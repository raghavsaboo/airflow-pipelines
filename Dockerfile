FROM puckel/docker-airflow
USER root
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt
