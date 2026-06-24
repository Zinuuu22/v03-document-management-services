# FROM python:3.10-slim

# ENV PYTHONUNBUFFERED=1 \
#     PYTHONDONTWRITEBYTECODE=1

# WORKDIR /app

# # 1. Cài các package hệ thống (nặng) — sẽ được cache
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     libpq-dev \
#     libreoffice \
#     libreoffice-writer \
#     && rm -rf /var/lib/apt/lists/*

# # 2. Copy requirements trước, để pip install được cache
# COPY requirements.txt .

# # 3. Cài pip packages — chỉ chạy lại khi requirements.txt thay đổi
# RUN python -m pip install --upgrade pip==25.3.* wheel setuptools \
#     && python -m pip install --no-cache-dir -r requirements.txt

# # 4. Cuối cùng mới COPY code — layer này build lại rất nhanh
# COPY . /app




FROM v03-base-services:1.0

RUN rm -rf ./*

COPY . .
