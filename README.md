# SaaS Image Resizer & Compressor (Flask + MinIO)

Aplikasi SaaS sederhana berbasis Flask untuk:
- Upload gambar
- Resize & compress gambar
- Penyimpanan file menggunakan S3-compatible storage (MinIO)

Project ini dijalankan menggunakan **Docker** dan **Docker Compose**.

---

## 1. Prasyarat

Pastikan VM / EC2 instance sudah memiliki:

- Docker
- Docker Compose
- Port terbuka:
  - `8080` → Aplikasi Flask
  - `9000` → MinIO API
  - `9001` → MinIO Console

---

## 2. Clone Repository

```bash
git clone https://github.com/uripsubagyo/saas-compress.git
cd saas-compress
```

## 3. Menjalankan MinIO (S3 Storage)

Jalankan MinIO menggunakan Docker:

```bash
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin123 \
  -v minio_data:/data \
  minio/minio server /data --console-address ":9001"
```

## 4. Build dan Jalankan Aplikasi Flask

```bash
docker-compose down
docker-compose up -d --build
```
