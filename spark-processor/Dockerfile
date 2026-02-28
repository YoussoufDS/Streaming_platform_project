FROM apache/spark:3.4.1
USER root
RUN pip install pymongo psycopg2-binary --no-cache-dir
COPY processor.py /app/processor.py
WORKDIR /app
CMD ["/opt/spark/bin/spark-submit", \
     "--packages", \
     "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,org.mongodb.spark:mongo-spark-connector_2.12:10.2.0,org.postgresql:postgresql:42.6.0", \
     "processor.py"]