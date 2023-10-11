# python image
FROM python:3.9-slim-buster

# Working directory
WORKDIR /usr/src/app

# environment variables
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends

RUN pip install --upgrade pip pipenv

# copy code
COPY . .

# Install packages
RUN pip install --no-cache-dir wheel
RUN pip install --no-cache-dir -r requirements.txt
