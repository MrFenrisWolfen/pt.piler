# Basis-Image von Piler verwenden
FROM sutoj/piler:1.4.7

# Pakete für debug installieren
# RUN apt update && apt install -y tree
# RUN apt update && apt install -y nano

# Arbeitsverzeichnis setzen (damit die Dateien am richtigen Ort landen)
WORKDIR /var/tmp

RUN mkdir /var/scripts

# Skripte ins Image kopieren
COPY start.sh /start.sh
COPY script-all.py /var/scripts/script-all.py
COPY script-24h.py /var/scripts/script-24h.py
COPY accounts.txt /var/scripts/accounts.txt

# Sicherstellen, dass die Skripte ausführbar sind
RUN chmod +x /start.sh
RUN chmod +x /var/scripts/script-*.py
RUN chmod 777 /var/scripts
RUN mkdir /var/tmp/emails
RUN chmod 777 /var/tmp/emails

    # Cronjob hinzufügen, ohne bestehende Crontab zu überschreiben
RUN crontab -l -u piler > /tmp/mycron \
    && echo "*/15 * * * * /usr/bin/python3 /var/scripts/script-24h.py >> /var/scripts/script-24h.log 2>&1" >> /tmp/mycron \
    && echo "0 0 * * 0 /usr/bin/python3 /var/scripts/script-all.py >> /var/scripts/script-all.log 2>&1" >> /tmp/mycron \
    && crontab -u piler /tmp/mycron \
    && rm /tmp/mycron


# Cron im Hintergrund starten und dann den normalen Containerprozess
CMD service cron start && /start.sh
