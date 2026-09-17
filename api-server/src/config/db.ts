import mongoose from 'mongoose';

const connectDB = async (): Promise<void> => {
  const mongoURI = process.env.MONGODB_URI || 'mongodb://localhost:27017/aadhaar_db';
  try {
    await mongoose.connect(mongoURI);
    console.log(`[MongoDB] Connected successfully to ${mongoURI}`);
  } catch (error: any) {
    console.error(`[MongoDB] Connection error: ${error.message}`);
    console.log('[MongoDB] Retrying connection in 5 seconds...');
    setTimeout(connectDB, 5000);
  }
};

export default connectDB;
