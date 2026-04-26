#!/bin/bash

# =============================================================================
# Script para limpieza de Idempotencia - 402 FastFood
# Configurar este script en el crontab del VPS
# Ejemplo: 0 * * * * /ruta/al/proyecto/cron_cleanup_idempotency.sh >> /ruta/al/proyecto/cron.log 2>&1
# =============================================================================

# Directorio del proyecto (ajustar según sea necesario)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Activar el entorno virtual (ajustar nombre del venv si es diferente)
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Ejecutar el comando de limpieza
python manage.py clear_expired_idempotency

# Desactivar entorno
deactivate 2>/dev/null || true

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Limpieza de idempotencia completada."
