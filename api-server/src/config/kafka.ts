import fs from 'fs';
import { Kafka, logLevel, Producer, SASLOptions } from 'kafkajs';

export interface TaskPayload {
  taskId: string;
  originalFilename: string;
  fileType: string;
  originalFilePath: string;
  status?: string;
  createdAt?: string;
}

const broker = process.env.KAFKA_BROKER || 'localhost:9092';
export const topic = process.env.KAFKA_TOPIC || 'aadhaar-masking-tasks';

const readEnvOrFile = (envVal?: string, filePath?: string): string | undefined => {
  if (filePath && fs.existsSync(filePath)) {
    return fs.readFileSync(filePath, 'utf-8');
  }
  return envVal;
};

const getSSLConfig = () => {
  const protocol = (process.env.KAFKA_SECURITY_PROTOCOL || '').toUpperCase();
  const ca = readEnvOrFile(process.env.KAFKA_CA_CERT, process.env.KAFKA_CA_CERT_PATH);
  const cert = readEnvOrFile(process.env.KAFKA_ACCESS_CERT, process.env.KAFKA_ACCESS_CERT_PATH);
  const key = readEnvOrFile(process.env.KAFKA_ACCESS_KEY, process.env.KAFKA_ACCESS_KEY_PATH);

  if (protocol === 'SSL') {
    return {
      rejectUnauthorized: process.env.KAFKA_REJECT_UNAUTHORIZED !== 'false',
      ca: ca ? [ca] : undefined,
      cert: cert || undefined,
      key: key || undefined,
    };
  }

  if (protocol === 'SASL_SSL') {
    if (ca) {
      return {
        rejectUnauthorized: process.env.KAFKA_REJECT_UNAUTHORIZED !== 'false',
        ca: [ca],
      };
    }
    return true;
  }

  if (ca || cert || key) {
    return {
      rejectUnauthorized: process.env.KAFKA_REJECT_UNAUTHORIZED !== 'false',
      ca: ca ? [ca] : undefined,
      cert: cert || undefined,
      key: key || undefined,
    };
  }

  return undefined;
};

const getSASLConfig = (): SASLOptions | undefined => {
  const protocol = (process.env.KAFKA_SECURITY_PROTOCOL || '').toUpperCase();
  const username = process.env.KAFKA_SASL_USERNAME;
  const password = process.env.KAFKA_SASL_PASSWORD;

  if (protocol.startsWith('SASL') || username) {
    const mechanism = (process.env.KAFKA_SASL_MECHANISM || 'scram-sha-256').toLowerCase() as any;
    return {
      mechanism,
      username: username || '',
      password: password || '',
    };
  }

  return undefined;
};

export const kafka = new Kafka({
  clientId: 'aadhaar-api-server',
  brokers: [broker],
  ssl: getSSLConfig(),
  sasl: getSASLConfig(),
  logLevel: logLevel.NOTHING,
  retry: {
    initialRetryTime: 300,
    retries: 8
  }
});

export const producer: Producer = kafka.producer();
let isConnected = false;

export const connectProducer = async (): Promise<void> => {
  if (isConnected) return;
  try {
    await producer.connect();
    isConnected = true;
    console.log(`[Kafka Producer] Connected to broker ${broker}`);
  } catch (err: any) {
    console.error(`[Kafka Producer] Connection failed: ${err.message}`);
    isConnected = false;
  }
};

export const pushTaskToKafka = async (taskPayload: TaskPayload): Promise<void> => {
  if (!isConnected) {
    await connectProducer();
  }
  if (!isConnected) {
    throw new Error('Kafka Producer is not connected. Unable to publish task event.');
  }

  await producer.send({
    topic,
    messages: [
      {
        key: taskPayload.taskId,
        value: JSON.stringify(taskPayload)
      }
    ]
  });

  console.log(`[Kafka Producer] Task ${taskPayload.taskId} pushed to topic '${topic}'`);
};
