#!/bin/bash
docker-compose down
docker-compose build --no-cache --progress=plain
docker-compose up --build
