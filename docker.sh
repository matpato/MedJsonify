#!/bin/bash
docker-compose down -v
docker-compose build --no-cache --progress=plain
docker-compose up --build
