gunicorn -w 4 -b 0.0.0.0:5002 app:app

DOCKER_BUILDKIT=1 docker build -t v03-document-management-services-dev:1.0 .
DOCKER_BUILDKIT=1 docker build -t v03-document-management-services-prod:1.0 .

# dev

docker compose -f docker-compose.dev.yaml up -d
docker compose -f docker-compose.dev.yaml down

# prod

docker compose -f docker-compose.prod.yaml up -d
docker compose -f docker-compose.prod.yaml down
