FROM python:3.13-slim


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1


WORKDIR /app


RUN addgroup --system app \
    && adduser \
        --system \
        --ingroup app \
        app


COPY requirements.txt .


RUN pip install --upgrade pip \
    && pip install -r requirements.txt


COPY . .


RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /app/staticfiles \
    && chown -R app:app /app


USER app


EXPOSE 8000


ENTRYPOINT ["/app/entrypoint.sh"]