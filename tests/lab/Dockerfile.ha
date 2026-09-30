ARG HA_BASE
FROM ${HA_BASE}
RUN apk add --no-cache iproute2
COPY .lab/tls/cloud.crt /usr/local/share/ca-certificates/velux-lab.crt
RUN update-ca-certificates
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
COPY tests/lab/gate.py /lab/gate.py
COPY tests/lab/configuration.yaml /lab/configuration.yaml
COPY tests/fixtures/legacy_storage.json /lab/legacy_storage.json
COPY dist/velux_active.zip /opt/velux-active/velux_active.zip
RUN python3 -m zipfile -e /opt/velux-active/velux_active.zip /opt/velux-active/integration
