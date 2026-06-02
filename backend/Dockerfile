FROM python:3.13-slim

RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# костыль 
COPY . . 

CMD ["uvicorn", "backend.app.api:api", "--host", "0.0.0.0", "--port", "8000"]