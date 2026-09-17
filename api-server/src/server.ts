import express, { Application, Request, Response } from 'express';
import cors from 'cors';
import path from 'path';
import dotenv from 'dotenv';

dotenv.config({ path: path.join(__dirname, '../../.env') });

import connectDB from './config/db';
import { connectProducer } from './config/kafka';
import taskRoutes from './routes/taskRoutes';

import fs from 'fs';

const app: Application = express();
const PORT: string | number = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve static files from dist/public or src/public
const distPublicPath = path.join(__dirname, 'public');
const srcPublicPath = path.join(__dirname, '../src/public');
const publicPath = fs.existsSync(distPublicPath) ? distPublicPath : srcPublicPath;

app.use(express.static(publicPath));

// Explicit Root Route handler to serve index.html
app.get('/', (req: Request, res: Response) => {
  const indexPath = path.join(publicPath, 'index.html');
  if (fs.existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    res.status(404).send('Index.html not found.');
  }
});

app.use('/api', taskRoutes);

app.get('/health', (req: Request, res: Response) => {
  res.json({ status: 'UP', service: 'Aadhaar Masking API Server (TypeScript)' });
});


const startServer = async (): Promise<void> => {
  await connectDB();
  await connectProducer();

  app.listen(PORT, () => {
    console.log(`[API Server - TypeScript] Running on http://localhost:${PORT}`);
  });
};

startServer();
