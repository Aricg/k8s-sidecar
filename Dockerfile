FROM        python:3.7-slim
WORKDIR     /app
COPY        requirements.txt .
RUN         pip install -r requirements.txt
RUN         groupadd -r -g 1000 jenkins && useradd -r -u 1000 -g jenkins jenkins
USER        root
RUN         chown -R jenkins:jenkins /app
RUN         apt-get update && apt-get install -y curl
COPY        sidecar/* ./
RUN         chmod 700 /app
ENV         PYTHONUNBUFFERED=1
USER        jenkins
CMD         [ "python", "-u", "/app/sidecar.py" ]