ARG HA_BASE
FROM ${HA_BASE}
ARG CLIENT_WHEEL_FILENAME
RUN apk add --no-cache iproute2
COPY .lab/tls/cloud.crt /usr/local/share/ca-certificates/velux-lab.crt
RUN update-ca-certificates
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
COPY tests/lab/gate.py /lab/gate.py
COPY tests/lab/legacy.py /lab/legacy.py
COPY tests/lab/configuration.yaml /lab/configuration.yaml
COPY tests/lab/probe /lab/probe
COPY tests/fixtures/legacy_storage.json /lab/legacy_storage.json
COPY .lab/legacy-recorder.db /lab/legacy-recorder.db
COPY scripts/cloud_smoke.py /lab/cloud_smoke.py
COPY dist/client/${CLIENT_WHEEL_FILENAME} /opt/velux-active/${CLIENT_WHEEL_FILENAME}
RUN uv pip install --no-index --no-deps --python /usr/local/bin/python3 /opt/velux-active/*.whl
COPY dist/velux_active.zip /opt/velux-active/velux_active.zip
RUN python3 -m zipfile -e /opt/velux-active/velux_active.zip /opt/velux-active/integration
