import { Request, Response } from 'express';
import { v4 as uuidv4 } from 'uuid';
import path from 'path';
import fs from 'fs';
import Task, { ITask } from '../models/Task';
import { pushTaskToKafka } from '../config/kafka';

export const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.pdf', '.txt'];

export const uploadFile = async (req: Request, res: Response): Promise<Response> => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded. Please select a file.' });
    }

    const fileExt = path.extname(req.file.originalname).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(fileExt)) {
      if (fs.existsSync(req.file.path)) {
        fs.unlinkSync(req.file.path);
      }
      return res.status(400).json({
        error: `Invalid file type '${fileExt}'. Supported types: ${ALLOWED_EXTENSIONS.join(', ')}`
      });
    }

    const taskId = uuidv4();
    const taskPayload = {
      taskId,
      originalFilename: req.file.originalname,
      fileType: req.file.mimetype || fileExt,
      originalFilePath: req.file.path,
      status: 'PENDING' as const,
      createdAt: new Date().toISOString()
    };

    const task: ITask = new Task(taskPayload);
    await task.save();

    try {
      await pushTaskToKafka({
        taskId,
        originalFilename: req.file.originalname,
        fileType: req.file.mimetype || fileExt,
        originalFilePath: req.file.path
      });
    } catch (kafkaError: any) {
      console.warn(`[API Server] Kafka push warning: ${kafkaError.message}`);
    }

    return res.status(202).json({
      message: 'File uploaded successfully and queued for processing.',
      taskId,
      status: 'PENDING'
    });
  } catch (err: any) {
    console.error(`[uploadFile Error]:`, err);
    return res.status(500).json({ error: 'Internal server error during file upload.' });
  }
};

export const getTaskStatus = async (req: Request, res: Response): Promise<Response> => {
  try {
    const { taskId } = req.params;
    const task = await Task.findOne({ taskId });

    if (!task) {
      return res.status(404).json({ error: `Task with ID '${taskId}' not found.` });
    }

    if (task.status === 'COMPLETED') {
      return res.json({
        taskId: task.taskId,
        status: 'COMPLETED',
        originalFilename: task.originalFilename,
        downloadUrl: `api/tasks/${task.taskId}/download`,
        completedAt: task.updatedAt
      });
    } else if (task.status === 'FAILED') {
      return res.json({
        taskId: task.taskId,
        status: 'FAILED',
        error: task.error || 'Aadhaar masking task failed.'
      });
    } else {
      return res.json({
        taskId: task.taskId,
        status: 'in progress',
        currentStep: task.status
      });
    }
  } catch (err: any) {
    console.error(`[getTaskStatus Error]:`, err);
    return res.status(500).json({ error: 'Internal server error while fetching task status.' });
  }
};

export const updateTaskStatus = async (req: Request, res: Response): Promise<Response> => {
  try {
    const { taskId } = req.params;
    const { status, maskedFilePath, error } = req.body;

    if (!['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED'].includes(status)) {
      return res.status(400).json({ error: 'Invalid status value.' });
    }

    const updateFields: Record<string, any> = { status };
    if (maskedFilePath) updateFields.maskedFilePath = maskedFilePath;
    if (error !== undefined) updateFields.error = error;

    const task = await Task.findOneAndUpdate(
      { taskId },
      { $set: updateFields },
      { new: true }
    );

    if (!task) {
      return res.status(404).json({ error: `Task with ID '${taskId}' not found.` });
    }

    return res.json({
      message: 'Task status updated successfully',
      task
    });
  } catch (err: any) {
    console.error(`[updateTaskStatus Error]:`, err);
    return res.status(500).json({ error: 'Internal server error while updating task status.' });
  }
};

export const downloadMaskedFile = async (req: Request, res: Response): Promise<void | Response> => {
  try {
    const { taskId } = req.params;
    const task = await Task.findOne({ taskId });

    if (!task) {
      return res.status(404).json({ error: `Task with ID '${taskId}' not found.` });
    }

    if (task.status !== 'COMPLETED') {
      return res.status(400).json({
        error: `File is not ready for download. Current status: ${task.status}`
      });
    }

    if (!task.maskedFilePath || !fs.existsSync(task.maskedFilePath)) {
      return res.status(404).json({ error: 'Masked output file not found on server storage.' });
    }

    const maskedFilename = `masked_${task.originalFilename}`;
    return res.download(task.maskedFilePath, maskedFilename);
  } catch (err: any) {
    console.error(`[downloadMaskedFile Error]:`, err);
    return res.status(500).json({ error: 'Internal server error downloading masked file.' });
  }
};
