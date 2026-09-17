import express, { Router } from 'express';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import {
  uploadFile,
  getTaskStatus,
  updateTaskStatus,
  downloadMaskedFile
} from '../controllers/taskController';

const router: Router = express.Router();

const uploadBaseDir = process.env.UPLOAD_DIR || path.join(__dirname, '../../uploads');
const originalUploadDir = path.join(uploadBaseDir, 'original');

if (!fs.existsSync(originalUploadDir)) {
  fs.mkdirSync(originalUploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, originalUploadDir);
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
    const ext = path.extname(file.originalname);
    cb(null, file.fieldname + '-' + uniqueSuffix + ext);
  }
});

const upload = multer({
  storage,
  limits: { fileSize: 20 * 1024 * 1024 }
});

router.post('/upload', upload.single('file'), uploadFile);
router.get('/tasks/:taskId', getTaskStatus);
router.patch('/tasks/:taskId/status', updateTaskStatus);
router.get('/tasks/:taskId/download', downloadMaskedFile);

export default router;
