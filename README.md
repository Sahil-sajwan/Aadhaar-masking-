# Aadhaar Masking Microservices Project

An asynchronous, event-driven Aadhaar masking microservices system built using **Node.js**, **Python**, **Apache Kafka**, and **MongoDB**.

---

## Features

- **Node.js API Server**:
  - `POST /api/upload`: Upload document/image, validate file type, create task in DB (`PENDING`), push message to Kafka, return `taskId`.
  - `GET /api/tasks/:taskId`: Fetch task status (`in progress`, `COMPLETED`, or `FAILED`).
  - `PATCH /api/tasks/:taskId/status`: Update task status in DB.
  - `GET /api/tasks/:taskId/download`: Download masked output file.
  - **Interactive Web UI**: Modern dashboard available at `http://localhost:3000` for visual file uploading, status monitoring, and downloading.

- **Python Aadhaar Masking Worker**:
  - Consumes tasks asynchronously from Kafka topic `aadhaar-masking-tasks`.
  - Updates task status in MongoDB (`IN_PROGRESS`).
  - Detects 12-digit Aadhaar numbers (Verhoeff checksum algorithm validated) in `.txt`, `.png`, `.jpg`, and `.pdf` files.
  - Masks the first 8 digits (e.g. `1234 5678 9012` -> `XXXX XXXX 9012`).
  - Updates MongoDB task record with `status: COMPLETED` and `maskedFilePath`.

- **Apache Kafka Queue**: Decouples API server and background processing worker for high throughput.
- **MongoDB**: Centralized storage for task metadata and status tracking.

## Getting Started

### Run with Docker Compose (Recommended)

1. Start all containers (MongoDB, Kafka [KRaft mode], API Server, Python Worker):
   ```bash
   docker-compose up --build
   ```

2. Access the Web Dashboard in your browser:
   `http://localhost:3000`


## API Endpoints Reference

### 1. Upload File & Create Task
- **Endpoint**: `POST /api/upload`
- **Body**: `multipart/form-data` with key `file` (Supports `.jpg`, `.png`, `.pdf`, `.txt`)
- **Response**:
  ```json
  {
    "message": "File uploaded successfully and queued for processing.",
    "taskId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "PENDING"
  }
  ```

### 2. Fetch Task Status
- **Endpoint**: `GET /api/tasks/:taskId`
- **Response (In Progress)**:
  ```json
  {
    "taskId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "in progress",
    "currentStep": "IN_PROGRESS"
  }
  ```
- **Response (Completed)**:
  ```json
  {
    "taskId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "COMPLETED",
    "originalFilename": "sample_aadhaar.txt",
    "downloadUrl": "/api/tasks/550e8400-e29b-41d4-a716-446655440000/download"
  }
  ```

### 3. Update Task Status
- **Endpoint**: `PATCH /api/tasks/:taskId/status`
- **Body**: `json`
  ```json
  {
    "status": "COMPLETED",
    "maskedFilePath": "./uploads/masked/masked_sample.txt"
  }
  ```

### 4. Download Masked File
- **Endpoint**: `GET /api/tasks/:taskId/download`
- Streams the processed masked output file for download.

---

## Production Deployment on AWS EC2 (Aiven Kafka & MongoDB Atlas)

To deploy the **API Server** and **Python Worker** on AWS EC2 using managed **Aiven Kafka** and **MongoDB Atlas**:

### 1. Prerequisites on EC2
- Install Docker and Docker Compose on your EC2 instance (Ubuntu/Debian):
  ```bash
  sudo apt-get update
  sudo apt-get install -y docker.io docker-compose
  sudo usermod -aG docker $USER
  ```

### 2. Configure Environment & Certificates
1. Create a `certs` directory on your EC2 instance and download your Aiven Kafka SSL certificates:
   ```bash
   mkdir -p certs
   # Place ca.pem, service.cert, and service.key inside ./certs/
   ```
2. Create a `.env` file based on `.env.example`:
   ```env
   PORT=3000
   MONGODB_URI=mongodb+srv://<user>:<password>@cluster0.xxx.mongodb.net/aadhaar_db?retryWrites=true&w=majority
   
   KAFKA_BROKER=kafka-xxxx-your-project.aivencloud.com:23180
   KAFKA_TOPIC=aadhaar-masking-tasks
   KAFKA_GROUP_ID=aadhaar-masking-group
   KAFKA_SECURITY_PROTOCOL=SSL
   KAFKA_CA_CERT_PATH=/app/certs/ca.pem
   KAFKA_ACCESS_CERT_PATH=/app/certs/service.cert
   KAFKA_ACCESS_KEY_PATH=/app/certs/service.key
   ```

### 3. Deploy via Docker Compose
Run the production EC2 docker-compose configuration:
```bash
docker compose -f docker-compose.ec2.yml up -d --build
```

Check logs:
```bash
docker compose -f docker-compose.ec2.yml logs -f
```

