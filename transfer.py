import os
import uuid
import time
import csv
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from fintoc import Fintoc

LIMITE_POR_TRANSFERENCIA = 7_000_000
ESTADOS_FINALES = {"succeeded", "failed", "rejected", "returned"}

load_dotenv()

api_key = os.getenv("FINTOC_API_KEY")
jws_private_key_path = os.getenv("JWS_PRIVATE_KEY_PATH")

if not api_key or not jws_private_key_path:
    raise ValueError("Faltan variables de entorno: FINTOC_API_KEY o JWS_PRIVATE_KEY_PATH")

with open(jws_private_key_path, "r") as f:
    jws_private_key = f.read()

client = Fintoc(api_key=api_key, jws_private_key=jws_private_key)

BANCOS = {
    "1":  ("Banco Estado", "cl_banco_estado"),
    "2":  ("Banco BCI", "cl_banco_bci"),
    "3":  ("Banco BICE", "cl_banco_bice"),
    "4":  ("Banco de Chile", "cl_banco_de_chile"),
    "5":  ("Banco Falabella", "cl_banco_falabella"),
    "6":  ("Banco Itaú", "cl_banco_itau"),
    "7":  ("Banco Ripley", "cl_banco_ripley"),
    "8":  ("Banco Santander", "cl_banco_santander"),
    "9":  ("Banco Consorcio", "cl_banco_consorcio"),
    "10": ("Scotiabank", "cl_banco_scotiabank"),
    "11": ("Mercado Pago", "cl_mercado_pago"),
    "12": ("Mach", "cl_mach"),
    "13": ("Tenpo", "cl_tenpo"),
    "14": ("Banco Security", "cl_banco_security"),
    "15": ("Tapp", "cl_tapp_caja_los_andes"),
    "16": ("Banco Internacional", "cl_banco_internacional"),
    "17": ("Coopeuch", "cl_banco_coopeuch"),
    "18": ("Copec Pay", "cl_copec_pay"),
    "19": ("Prepago Los Heroes", "cl_prepago_los_heroes"),
    "20": ("BBVA", "cl_banco_bbva"),
    "21": ("HSBC", "cl_banco_hsbc"),
}

# Helpers de input

def pedir(prompt, validar, error):
    while True:
        valor = input(prompt).strip()
        if validar(valor):
            return valor
        print(f"  {error}")

def pedir_int(prompt, error="Ingresa un número válido."):
    while True:
        try:
            valor = int(input(prompt).strip())
            if valor > 0:
                return valor
            print(f"  El monto debe ser mayor a 0.")
        except ValueError:
            print(f"  {error}")


# 1. Calcular chunks

def calcular_chunks(monto_total, limite_por_transferencia):
    chunks = []
    restante = monto_total
    while restante > 0:
        chunks.append(min(restante, limite_por_transferencia))
        restante -= limite_por_transferencia
    return chunks


# 2. Simular depósito si el balance es insuficiente

def asegurar_balance(account, monto_total):
    if account.available_balance >= monto_total:
        return True
    diferencia = monto_total - account.available_balance
    print(f"\nBalance insuficiente. Saldo actual: {account.available_balance:,} CLP | Necesitas: {monto_total:,} CLP (faltan {diferencia:,} CLP)")
    respuesta = input("¿Deseas agregar fondos a tu cuenta? (s/n): ").strip().lower()
    if respuesta != "s":
        print("Operación cancelada por balance insuficiente.")
        return False
    monto_deposito = pedir_int("¿Cuánto deseas agregar a tu cuenta? (CLP): ")
    print(f"Simulando depósito de {monto_deposito:,} CLP...")
    client.v2.simulate.receive_transfer(
        account_number_id=account.root_account_number_id,
        amount=monto_deposito,
        currency="CLP",
    )
    time.sleep(2)
    print(f"Fondos agregados exitosamente: +{monto_deposito:,} CLP\n")
    return True


# 3. Ejecutar transferencias

def ejecutar_transferencias(chunks, account_id, holder_id, holder_name, account_number, account_type, institution_id):
    transfers = []
    for i, amount in enumerate(chunks, start=1):
        print(f"Ejecutando transferencia {i}/{len(chunks)}: {amount:,} CLP...")
        try:
            transfer = client.v2.transfers.create(
                account_id=account_id,
                amount=amount,
                currency="CLP",
                idempotency_key=str(uuid.uuid4()),
                comment=f"Transferencia {i} de {len(chunks)}",
                counterparty={
                    "holder_id": holder_id,
                    "holder_name": holder_name,
                    "account_number": account_number,
                    "account_type": account_type,
                    "institution_id": institution_id,
                },
            )
            transfers.append({"transfer": transfer, "error": None})
        except Exception as e:
            print(f"  ✗ Error en transferencia {i}: {e}")
            transfers.append({"transfer": None, "error": str(e), "amount": amount})
    return transfers


# 4. Polling hasta estado final

def consultar_estados(transfer_results, intervalo=3, max_intentos=20):
    print("\nConsultando estados finales...\n")
    resultados = []

    for item in transfer_results:
        if item["transfer"] is None:
            resultados.append({
                "id": None,
                "amount": item["amount"],
                "status": "error_creacion",
                "transaction_date": None,
                "error": item["error"],
            })
            continue

        transfer = item["transfer"]
        transfer_id = transfer.id

        for _ in range(max_intentos):
            fetched = client.v2.transfers.get(transfer_id)
            if fetched.status in ESTADOS_FINALES:
                break
            time.sleep(intervalo)

        resultados.append({
            "id": fetched.id,
            "amount": fetched.amount,
            "status": fetched.status,
            "transaction_date": fetched.transaction_date,
            "error": None,
        })
        print(f"  {fetched.id}: {fetched.status} — {fetched.amount:,} CLP")

    return resultados


# 5. Generar reporte CSV

def generar_reporte(resultados):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    Path("reportes").mkdir(exist_ok=True)
    filename = f"reportes/reporte_transferencias_{timestamp}.csv"
    campos = ["id", "amount", "status", "transaction_date", "error"]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(resultados)

    completadas = sum(1 for r in resultados if r["status"] == "succeeded")
    fallidas = len(resultados) - completadas

    print(f"\nReporte generado: {filename}")
    print(f"  Completadas: {completadas} | Fallidas/Pendientes: {fallidas}")
    return filename


# Bloque principal

print("Obteniendo cuentas disponibles...\n")
accounts = list(client.v2.accounts.list())

for i, account in enumerate(accounts):
    label = account.description or ("\u2022\u2022" + account.root_account_number[-4:])
    print(f"  [{i + 1}] {label} — Balance: {account.available_balance:,} CLP")
print()

if len(accounts) > 1:
    opcion = pedir(
        f"Elige cuenta origen (1-{len(accounts)}): ",
        lambda v: v.isdigit() and 1 <= int(v) <= len(accounts),
        f"Ingresa un número entre 1 y {len(accounts)}.",
    )
    idx = int(opcion) - 1
else:
    idx = 0

cuenta_origen = accounts[idx]
cuenta_label = cuenta_origen.description or ("\u2022\u2022" + cuenta_origen.root_account_number[-4:])
print(f"\nCuenta seleccionada: {cuenta_label}\n")

while True:
    print(f"Saldo disponible: {cuenta_origen.available_balance:,} CLP\n")
    monto_total = pedir_int("Monto total a transferir (CLP): ")
    print()
    if asegurar_balance(cuenta_origen, monto_total):
        break
    cuenta_origen = next(a for a in client.v2.accounts.list() if a.id == cuenta_origen.id)

holder_id      = pedir("RUT del destinatario: ",   bool, "El RUT no puede estar vacío.")
holder_name    = pedir("Nombre del destinatario: ", bool, "El nombre no puede estar vacío.")
account_number = pedir("Número de cuenta: ",        bool, "El número de cuenta no puede estar vacío.")

print("Tipo de cuenta: \n1) Cuenta corriente \n2) Cuenta vista\n")
opcion_tipo  = pedir("Elige una opción (1 o 2): ", lambda v: v in ("1", "2"), "Ingresa 1 o 2.")
account_type = {"1": "checking_account", "2": "sight_account"}[opcion_tipo]

print("\nBanco de destino:")
for k, (nombre, _) in BANCOS.items():
    print(f"  [{k}] {nombre}" if len(k) == 1 else f"  [{k}] {nombre}")
opcion_banco           = pedir("\nElige una opción: ", lambda v: v in BANCOS, f"Ingresa un número entre 1 y {len(BANCOS)}.")
banco_nombre, institution_id = BANCOS[opcion_banco]

chunks = calcular_chunks(monto_total, LIMITE_POR_TRANSFERENCIA)

tipo_cuenta_label = "Cuenta corriente" if account_type == "checking_account" else "Cuenta vista"

print(f"\n{'─' * 40}")
print(f"  Monto total:       {monto_total:,} CLP")
print(f"  Destinatario:      {holder_name} ({holder_id})")
print(f"  Cuenta destino:    {account_number} ({tipo_cuenta_label})")
print(f"  Banco:             {banco_nombre}")
print(f"  Transferencias:    {len(chunks)}")
print(f"{'─' * 40}\n")

confirmar = input("¿Confirmar ejecución? (s/n): ").strip().lower()
if confirmar != "s":
    print("Operación cancelada.")
    exit()

print()
transfer_results = ejecutar_transferencias(
    chunks,
    account_id=cuenta_origen.id,
    holder_id=holder_id,
    holder_name=holder_name,
    account_number=account_number,
    account_type=account_type,
    institution_id=institution_id,
)

resultados = consultar_estados(transfer_results)
generar_reporte(resultados)
