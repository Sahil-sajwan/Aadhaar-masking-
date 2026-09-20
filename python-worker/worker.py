import os
import json
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from kafka import KafkaConsumer
from utils.aadhaar_masker import AadhaarMasker

load_dotenv()

MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/aadhaar_db')
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'aadhaar-masking-tasks')
KAFKA_GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'aadhaar-masking-group')
UPLOAD_DIR = os.getenv('UPLOAD_DIR', './uploads')

# MongoDB Client Setup
def get_db_client():
    while True:
        try:
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            sanitized_uri = MONGODB_URI.split('@')[-1] if '@' in MONGODB_URI else MONGODB_URI
            print(f"[Python Worker] Connected to MongoDB at {sanitized_uri}")
            try:
                db = client.get_default_database()
            except Exception:
                db = client['aadhaar_db']
            return db
        except Exception as e:
            print(f"[Python Worker] MongoDB connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5)

# Kafka Consumer Setup
def get_kafka_consumer():
    while True:
        try:
            security_protocol = os.getenv('KAFKA_SECURITY_PROTOCOL', 'PLAINTEXT').upper()
            
            kafka_kwargs = {
                "bootstrap_servers": [KAFKA_BROKER],
                "group_id": KAFKA_GROUP_ID,
                "value_deserializer": lambda m: json.loads(m.decode('utf-8')),
                "auto_offset_reset": 'earliest',
                "enable_auto_commit": True,
                "security_protocol": security_protocol,
            }

            ca_path = os.getenv('KAFKA_CA_CERT_PATH')
            cert_path = os.getenv('KAFKA_ACCESS_CERT_PATH')
            key_path = os.getenv('KAFKA_ACCESS_KEY_PATH')

            # Handle certificate raw string contents if provided
            if not ca_path and os.getenv('KAFKA_CA_CERT'):
                temp_ca = '/tmp/ca.pem'
                with open(temp_ca, 'w') as f:
                    f.write(os.getenv('KAFKA_CA_CERT'))
                ca_path = temp_ca

            if not cert_path and os.getenv('KAFKA_ACCESS_CERT'):
                temp_cert = '/tmp/service.cert'
                with open(temp_cert, 'w') as f:
                    f.write(os.getenv('KAFKA_ACCESS_CERT'))
                cert_path = temp_cert

            if not key_path and os.getenv('KAFKA_ACCESS_KEY'):
                temp_key = '/tmp/service.key'
                with open(temp_key, 'w') as f:
                    f.write(os.getenv('KAFKA_ACCESS_KEY'))
                key_path = temp_key

            if ca_path and os.path.exists(ca_path):
                kafka_kwargs['ssl_cafile'] = ca_path
            if cert_path and os.path.exists(cert_path):
                kafka_kwargs['ssl_certfile'] = cert_path
            if key_path and os.path.exists(key_path):
                kafka_kwargs['ssl_keyfile'] = key_path

            if security_protocol in ('SASL_SSL', 'SASL_PLAINTEXT'):
                kafka_kwargs['sasl_mechanism'] = os.getenv('KAFKA_SASL_MECHANISM', 'SCRAM-SHA-256').upper()
                kafka_kwargs['sasl_plain_username'] = os.getenv('KAFKA_SASL_USERNAME', '')
                kafka_kwargs['sasl_plain_password'] = os.getenv('KAFKA_SASL_PASSWORD', '')

            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                **kafka_kwargs
            )
            print(f"[Python Worker] Connected to Kafka broker {KAFKA_BROKER} ({security_protocol}), listening on topic '{KAFKA_TOPIC}'")
            return consumer
        except Exception as e:
            print(f"[Python Worker] Kafka connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def main():
    db = get_db_client()
    tasks_collection = db['tasks']
    consumer = get_kafka_consumer()

    print("[Python Worker] Aadhaar Masking Worker started and ready to process tasks...")

    for message in consumer:
        try:
            task_data = message.value
            task_id = task_data.get('taskId')
            original_file_path = task_data.get('originalFilePath')
            original_filename = task_data.get('originalFilename')

            print(f"\n[Python Worker] Received task {task_id} for file '{original_filename}'")

            # 1) Update task status to IN_PROGRESS in MongoDB
            tasks_collection.update_one(
                {'taskId': task_id},
                {'$set': {'status': 'IN_PROGRESS', 'updatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ')}}
            )

            # Define output path for masked file
            masked_dir = os.path.join(UPLOAD_DIR, 'masked')
            os.makedirs(masked_dir, exist_ok=True)
            masked_filename = f"masked_{os.path.basename(original_file_path)}"
            masked_file_path = os.path.join(masked_dir, masked_filename)

            # 2) Process Aadhaar masking
            print(f"[Python Worker] Processing masking for '{original_file_path}'...")
            AadhaarMasker.mask_file(original_file_path, masked_file_path)

            # 3) Delete the raw original file to preserve privacy and store only the masked file
            if os.path.exists(original_file_path):
                try:
                    os.remove(original_file_path)
                    print(f"[Python Worker] Deleted raw unmasked file: '{original_file_path}'")
                except Exception as del_err:
                    print(f"[Python Worker] Warning: Failed to delete raw file '{original_file_path}': {del_err}")

            # 4) Update task status to COMPLETED in MongoDB
            tasks_collection.update_one(
                {'taskId': task_id},
                {
                    '$set': {
                        'status': 'COMPLETED',
                        'maskedFilePath': masked_file_path,
                        'updatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ')
                    }
                }
            )
            print(f"[Python Worker] Task {task_id} COMPLETED successfully. Masked file: '{masked_file_path}'")


        except Exception as err:
            error_msg = str(err)
            print(f"[Python Worker] ERROR processing task {task_id}: {error_msg}")

            # Delete raw original file if it exists to preserve privacy even when masking fails
            if original_file_path and os.path.exists(original_file_path):
                try:
                    os.remove(original_file_path)
                    print(f"[Python Worker] Deleted raw file after error: '{original_file_path}'")
                except Exception as del_err:
                    print(f"[Python Worker] Warning: Failed to delete raw file '{original_file_path}': {del_err}")

            tasks_collection.update_one(
                {'taskId': task_id},
                {
                    '$set': {
                        'status': 'FAILED',
                        'error': error_msg,
                        'updatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ')
                    }
                }
            )


if __name__ == '__main__':
    main()
