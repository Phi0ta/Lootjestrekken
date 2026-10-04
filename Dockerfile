FROM python:3.14

WORKDIR /app

COPY /app .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

CMD ["fastapi", "run", "main.py", "--port", "8000"]