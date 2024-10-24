FROM ubuntu:22.04
WORKDIR /home/slips
RUN apt-get update && apt-get install -y python3 python3-pip
RUN pip3 install flask==3.0.3 \
    && pip3 install pandas==1.5.3 \
    && pip3 install sqlalchemy==2.0.31 \
    && pip3 install werkzeug==3.0.4 \
    && pip3 install concurrent_log_handler==0.9.25 \
    && pip3 install numpy==1.25.2 \
    && pip3 install flask_sqlalchemy==3.1.1 \
    && pip3 install pymysql==1.1.1 \
    && pip3 install tables==3.9.1 \
    && pip3 install requests==2.32.3
COPY slips_data_svc.py .
COPY templates ./templates
COPY config.py .
EXPOSE 5000
CMD ["python3", "slips_data_svc.py"]