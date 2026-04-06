# Fintoc Transfers

Script en Python para ejecutar transferencias de alto monto usando la API de Transfers de Fintoc. Dado que Chile tiene un límite de $7.000.000 por transferencia, el script divide automáticamente el monto total en los chunks necesarios y los ejecuta secuencialmente.

## Requisitos

- Python 3.10+
- Cuenta en [Fintoc](https://fintoc.com) con el producto Transfers habilitado en modo Test
- API Key y clave privada JWS generados desde el dashboard de Fintoc

## Instalación

```bash
pip install fintoc python-dotenv
```

## Configuración

1. Copia el archivo de ejemplo y completa tus credenciales:

```bash
cp .env.example .env
```

2. Edita `.env` con tu API Key y la ruta a tu clave privada JWS:

```
FINTOC_API_KEY=tu_api_key_aqui
JWS_PRIVATE_KEY_PATH=./private_key.pem
ACCOUNT_NUMBER_ID=tu_account_number_id_aqui
```

## Uso

```bash
python transfer.py
```

El script te guiará interactivamente para:

1. Seleccionar la cuenta de origen
2. Ingresar el monto total a transferir
3. Ingresar los datos del destinatario (RUT, nombre, número de cuenta, tipo de cuenta, banco)
4. Confirmar la operación

Una vez confirmado, el script:
- Divide el monto en transferencias de hasta $7.000.000
- Ejecuta cada transferencia via API
- Consulta el estado final de cada una mediante polling
- Genera un reporte CSV en la carpeta `reportes/`

## Reporte

Cada ejecución genera un archivo `reportes/reporte_transferencias_YYYYMMDD_HHMMSS.csv` con el resultado de todas las transferencias:

| Campo | Descripción |
|---|---|
| `id` | ID de la transferencia en Fintoc |
| `amount` | Monto transferido en CLP |
| `status` | Estado final (`succeeded`, `failed`, `rejected`, `returned`) |
| `transaction_date` | Fecha de la transacción |
| `error` | Detalle del error si la transferencia falló |
