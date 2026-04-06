# 🚀 Terraform AWS ETL Pipeline

## 📌 Overview
This project demonstrates a simple DevOps pipeline using:
- Terraform (Infrastructure as Code)
- AWS S3
- GitHub Actions (CI/CD)
- Python ETL script

## 🧱 Architecture
GitHub → GitHub Actions → Terraform → AWS S3  
                                     ↓  
                                Python ETL Upload  

## ⚙️ Features
- Automated infrastructure provisioning
- CI/CD pipeline using GitHub Actions
- Python-based ETL job
- Data stored in S3 bucket

## 🚀 How to Run

### 1. Setup AWS Credentials
```bash
aws configure