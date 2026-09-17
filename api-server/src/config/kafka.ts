import { Kafka, logLevel, Producer } from 'kafkajs';

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

export const kafka = new Kafka({
  clientId: 'aadhaar-api-server',
  brokers: [broker],
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
