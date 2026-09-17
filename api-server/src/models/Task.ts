import mongoose, { Schema, Document } from 'mongoose';

export interface ITask extends Document {
  taskId: string;
  originalFilename: string;
  fileType: string;
  originalFilePath: string;
  maskedFilePath?: string | null;
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';
  error?: string | null;
  createdAt: Date;
  updatedAt: Date;
}

const taskSchema = new Schema<ITask>(
  {
    taskId: {
      type: String,
      required: true,
      unique: true,
      index: true
    },
    originalFilename: {
      type: String,
      required: true
    },
    fileType: {
      type: String,
      required: true
    },
    originalFilePath: {
      type: String,
      required: true
    },
    maskedFilePath: {
      type: String,
      default: null
    },
    status: {
      type: String,
      enum: ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED'],
      default: 'PENDING',
      required: true
    },
    error: {
      type: String,
      default: null
    }
  },
  {
    timestamps: true
  }
);

export default mongoose.model<ITask>('Task', taskSchema);
