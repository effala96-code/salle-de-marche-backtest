FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m ipykernel install --sys-prefix --name python3 --display-name "Python 3"

COPY src ./src
RUN mkdir -p /app/backtest \
    && useradd --create-home app \
    && chown -R app:app /app

USER app

CMD ["python", "-m", "papermill", "src/notebooks/notebooks.ipynb", "backtest/notebooks_execute.ipynb"]
