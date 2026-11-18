#!/usr/bin/env bash
# corrida.sh — corridas del laboratorio de congestión, en el computador A (como root).
#
# Uso:   bash corrida.sh prueba enp0s8     piloto corto (no entra al análisis)
#        bash corrida.sh c01 enp0s8        una corrida (c01 ... c06)
#        bash corrida.sh todas enp0s8      c01 → c06 en orden; se detiene si una falla
#        PERFIL=B bash corrida.sh ...      corridas de ~8 min en vez de ~16 (ver abajo)
#
# Hace, con el mismo reloj de A: captura (tcpdump), muestreo de la cola cada 0,05 s,
# las fases de iperf3 del calendario, el registro de la hora y de los descartes de cada
# fase, y la exportación de la traza a CSV. Todo queda en datos/<corrida>/. Si algo
# falla o se interrumpe con Ctrl+C, la carpeta se mueve a datos/fallidas/.

set -u

RUN="${1:-}"
IFACE="${2:-}"
# A = IPv4 de la interfaz de salida. B = servidor iperf3: B_IP si se da; si no, la
# puerta de enlace por defecto (en WSL2 es Windows, donde corre el servidor).
A="${A_IP:-$(ip -4 -o addr show dev "$IFACE" 2> /dev/null | awk '{split($4, a, "/"); print a[1]; exit}')}"
B="${B_IP:-$(ip route show default 2> /dev/null | awk '{print $3; exit}')}"
BASE_DIR="$(pwd)/datos"
OUT="$BASE_DIR/$RUN"
USUARIO="${SUDO_USER:-root}"

# Muestreo de la cola: cada 0,05 s en una grilla de tiempo fija. Con eso se pueden
# formar ventanas de 0,05 s, 0,1 s o 1 s (sumando ventanas consecutivas) sin recapturar.
MUESTREO=0.05
# Duración objetivo de tráfico por corrida (s). Con 6 corridas:
#   A: 950 s → ≈ 57 000 ventanas de 0,1 s      B: 480 s → ≈ 57 600 ventanas de 0,05 s
PERFIL="${PERFIL:-A}"
case "$PERFIL" in
  A) OBJETIVO=950 ;;
  B) OBJETIVO=480 ;;
  *) echo "PERFIL debe ser A o B" >&2; exit 1 ;;
esac

if [ "$RUN" = "todas" ]; then
  for c in c01 c02 c03 c04 c05 c06; do
    if [ -d "$BASE_DIR/$c" ]; then echo "== $c ya existe, se salta =="; continue; fi
    bash "$0" "$c" "$IFACE" || { echo "== Se detuvo en $c =="; exit 1; }
  done
  echo "== Las 6 corridas terminaron =="
  exit 0
fi

# ----------------------------------------------------------------------------------
# Calendario de cada corrida. Una fase por línea:  etiqueta  tasa_Mbit/s  duración_s
#   base / rec : carga baja (4–6 Mbit/s), sin descartes esperados.
#   rampa      : escalones 8 → 9 → 9.5 → (10 o 10.5) → tope de 12, 14 o 20. El límite
#                en carga ofrecida es ≈ 9.66 Mbit/s (trama de 1242 B por cada 1200 B).
#   salto      : desde recuperación directo a 12, 14, 20 o 30 Mbit/s.
# Los episodios van en pares (una rampa y un salto en orden aleatorio) hasta llegar a
# la duración objetivo. Orden, tasas y duraciones se sortean con una semilla fija por
# corrida: el calendario es reproducible y no lo elige a mano quien diseña.
# ----------------------------------------------------------------------------------
plan() {
  if [ "$1" = "prueba" ]; then
    printf 'base 4 5\nsalto 14 5\nrec 4 5\n'
    return 0
  fi
  case "$1" in c01|c02|c03|c04|c05|c06) ;; *) return 1 ;; esac
  python3 - "$1" "$OBJETIVO" <<'PY'
import random, sys
corrida, objetivo = sys.argv[1], float(sys.argv[2])
rng = random.Random("congestion-" + corrida)
fases = [("base", rng.choice([4, 5, 6]), rng.randint(15, 20))]
t, pendientes = fases[0][2], []
while t < objetivo:
    if not pendientes:
        pendientes = ["rampa", "salto"]
        rng.shuffle(pendientes)
    if pendientes.pop() == "rampa":
        d = rng.choice([3, 4, 5])
        ep = [("rampa", 8, d), ("rampa", 9, d), ("rampa", 9.5, d),
              ("rampa", rng.choice([10, 10, 10.5]), d),
              ("rampa", rng.choice([12, 14, 20]), rng.choice([6, 8, 10]))]
    else:
        ep = [("salto", rng.choice([12, 14, 20, 30]), rng.choice([8, 10, 12, 15]))]
    ep.append(("rec", rng.choice([4, 5, 6]), rng.randint(10, 15)))
    fases += ep
    t += sum(f[2] for f in ep)
for etq, tasa, dur in fases:
    print(etq, tasa, dur)
PY
}

falla() { echo "ERROR: $*" >&2; exit 1; }

# Descartes acumulados de la TBF, leídos de la salida textual de tc (rápido: se lee
# antes y después de cada fase y no debe alargar la pausa entre comandos).
drops_txt() {
  tc -s qdisc show dev "$IFACE" | awk '
    /^qdisc tbf 10:/ { f = 1; next }
    f { for (i = 1; i <= NF; i++) if ($i == "(dropped") { gsub(",", "", $(i+1)); print $(i+1); exit } }'
}

# Lo mismo leído del JSON (campo drops del objeto kind=tbf, handle=10:), como pide el
# enunciado. Se usa al inicio y al final para comprobar que ambas lecturas coinciden.
drops_json() {
  tc -j -s qdisc show dev "$IFACE" | python3 -c '
import json, sys
print(next(q["drops"] for q in json.load(sys.stdin)
           if q.get("kind") == "tbf" and q.get("handle") == "10:"))'
}

# ---------------------------- Comprobaciones previas ------------------------------
[ "$(id -u)" -eq 0 ] || falla "ejecútelo como root: bash corrida.sh $RUN $IFACE"
[ -n "$RUN" ] && [ -n "$IFACE" ] || falla "uso: bash corrida.sh <corrida> <interfaz>"
[ -n "$A" ] && [ -n "$B" ] || falla "no se pudo determinar la IP de A ($A) o de B ($B)"
PLAN_TXT="$(plan "$RUN")" || falla "no hay calendario para '$RUN' (use prueba, c01 ... c06)"
tc qdisc show dev "$IFACE" | grep -q '^qdisc tbf 10: root' \
  || falla "no está la cola TBF 10: en $IFACE (aplíquenla con tc qdisc replace ...)"
[ ! -e "$OUT" ] || falla "ya existe $OUT; si quieren repetirla, muevan esa carpeta"
ping -c 1 -W 1 "$B" > /dev/null || falla "B ($B) no responde al ping"

mkdir -p "$OUT"
echo "$PLAN_TXT" > "$OUT/${RUN}_plan.txt"
tc -s qdisc show dev "$IFACE" > "$OUT/${RUN}_tc_inicio.txt"
D_INI=$(drops_json)

PID_CAP=""
PID_COLA=""
terminar() {
  if [ -n "$PID_COLA" ]; then kill "$PID_COLA" 2> /dev/null; wait "$PID_COLA" 2> /dev/null; fi
  # SIGTERM y no SIGINT: en un script, los procesos en segundo plano ignoran SIGINT.
  # tcpdump atiende SIGTERM igual: vacía el archivo e imprime sus estadísticas.
  if [ -n "$PID_CAP" ]; then kill -TERM "$PID_CAP" 2> /dev/null; wait "$PID_CAP" 2> /dev/null; fi
  PID_COLA=""
  PID_CAP=""
}
abortar() {
  trap - INT TERM
  terminar
  mkdir -p "$BASE_DIR/fallidas"
  DEST="$BASE_DIR/fallidas/${RUN}_$(date +%H%M%S)"
  mv "$OUT" "$DEST"
  chown -R "$USUARIO": "$BASE_DIR"
  echo "Corrida $RUN abortada. Sus archivos quedaron en $DEST. Se puede repetir." >&2
  exit 1
}
trap abortar INT TERM

# ------------------------------------ Captura -------------------------------------
# -Z root: en Ubuntu, tcpdump deja de ser root antes de abrir el archivo de salida y
# no podría escribir en esta carpeta (creada por root).
tcpdump -i "$IFACE" -nn -s 96 -B 4096 -Z root -w "$OUT/$RUN.pcap" \
  "src host $A and dst host $B and udp dst port 5201" 2> "$OUT/${RUN}_tcpdump.txt" &
PID_CAP=$!
sleep 2
kill -0 "$PID_CAP" 2> /dev/null || { cat "$OUT/${RUN}_tcpdump.txt" >&2; abortar; }

# ------------------------------ Muestreo de la cola -------------------------------
# Mismo formato que el bucle del enunciado (cada muestra = una línea con el tiempo Unix
# y otra con el JSON de "tc -j -s"), pero cada MUESTREO segundos sobre una grilla fija.
# Un bucle con "sleep" se atrasa lo que tarda cada lectura; la grilla no acumula ese
# atraso. El tiempo anotado es el punto medio de la lectura de tc. Si una lectura se
# atrasa más de un periodo, se saltan las marcas perdidas y queda un Δ más largo,
# visible en el análisis como pausa anormal.
python3 - "$IFACE" "$MUESTREO" > "$OUT/${RUN}_cola.log" <<'PY' &
import subprocess, sys, time
iface, P = sys.argv[1], float(sys.argv[2])
cmd = ["tc", "-j", "-s", "qdisc", "show", "dev", iface]
t0, k = time.time(), 0
while True:
    k += 1
    ahora = time.time()
    marca = t0 + k * P
    if marca > ahora:
        time.sleep(marca - ahora)
    elif ahora - marca > P:
        k = int((ahora - t0) / P)
    a = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    b = time.time()
    if r.returncode != 0:
        break
    sys.stdout.write(f"{(a + b) / 2:.9f}\n{r.stdout.strip()}\n")
    sys.stdout.flush()
PY
PID_COLA=$!

sleep 5   # muestras sin tráfico antes de la primera fase

# ------------------------------------- Fases --------------------------------------
echo "fase,etiqueta,tasa_mbps,duracion_s,t_ini,t_fin,drops_ini,drops_fin" > "$OUT/${RUN}_fases.csv"
echo "== Corrida $RUN  A=$A → B=$B  ($(echo "$PLAN_TXT" | wc -l) fases, $(echo "$PLAN_TXT" | awk '{s+=$3} END{print s}') s de tráfico) =="
i=0
while read -r ETQ TASA DUR; do
  [ -z "${ETQ:-}" ] && continue
  i=$((i + 1))
  F=$(printf 'fase%02d' "$i")
  D0=$(drops_txt)
  T0=$(date +%s.%N)
  if ! iperf3 -c "$B" -u -b "${TASA}M" -l 1200 -t "$DUR" -i 1 --get-server-output -J \
       > "$OUT/${RUN}_${F}.json" < /dev/null; then
    echo "iperf3 falló en $F (ver $OUT/${RUN}_${F}.json)" >&2
    abortar
  fi
  T1=$(date +%s.%N)
  D1=$(drops_txt)
  echo "$F,$ETQ,$TASA,$DUR,$T0,$T1,$D0,$D1" >> "$OUT/${RUN}_fases.csv"
  printf '%s  %-5s %5s Mbit/s %3s s   descartes en la fase: %6d\n' \
    "$F" "$ETQ" "$TASA" "$DUR" $((D1 - D0))
done <<< "$PLAN_TXT"

sleep 5   # muestras sin tráfico después de la última fase
terminar
trap - INT TERM

# ---------------------------- Exportación y verificación ---------------------------
tc -s qdisc show dev "$IFACE" > "$OUT/${RUN}_tc_fin.txt"
# Traza → CSV (tiempo de cada paquete y longitud de trama). Con tshark si está
# instalado (comando del enunciado); si no, se lee el pcap directamente: el formato
# guarda por paquete su marca de tiempo y la longitud original de la trama (orig_len),
# que es lo mismo que tshark reporta como frame.time_epoch y frame.len.
if command -v tshark > /dev/null; then
  tshark -r "$OUT/$RUN.pcap" -T fields -E header=y -E separator=, \
    -e frame.time_epoch -e frame.len > "$OUT/${RUN}_paquetes.csv" 2> /dev/null
else
  python3 - "$OUT/$RUN.pcap" > "$OUT/${RUN}_paquetes.csv" <<'PY'
import struct, sys
f = open(sys.argv[1], "rb")
formatos = {b"\xd4\xc3\xb2\xa1": ("<", 6), b"\xa1\xb2\xc3\xd4": (">", 6),
            b"\x4d\x3c\xb2\xa1": ("<", 9), b"\xa1\xb2\x3c\x4d": (">", 9)}
magia = f.read(4)
if magia not in formatos:
    sys.exit("la traza no es pcap clásico")
orden, dec = formatos[magia]
f.read(20)                                    # resto de la cabecera global
reg = struct.Struct(orden + "IIII")           # ts_seg, ts_frac, incl_len, orig_len
print("frame.time_epoch,frame.len")
while True:
    h = f.read(16)
    if len(h) < 16:
        break
    seg, frac, incl, orig = reg.unpack(h)
    f.seek(incl, 1)
    print(f"{seg}.{frac:0{dec}d},{orig}")
PY
fi

D_FIN_JSON=$(drops_json)
D_FIN_TXT=$(drops_txt)
N_PAQ=$(($(wc -l < "$OUT/${RUN}_paquetes.csv") - 1))
N_COLA=$(grep -c '^\[' "$OUT/${RUN}_cola.log")

echo
echo "== Resumen $RUN =="
echo "Descartes TBF en la corrida:  $((D_FIN_JSON - D_INI))"
echo "Contador acumulado:  JSON = $D_FIN_JSON   texto (dropped) = $D_FIN_TXT"
[ "$D_FIN_JSON" = "$D_FIN_TXT" ] || echo "AVISO: el JSON y el texto de tc no coinciden"
echo "Paquetes en la traza: $N_PAQ   Muestras de cola: $N_COLA"
python3 - "$OUT/${RUN}_cola.log" <<'PY'
import sys
t = [float(l) for l in open(sys.argv[1]) if l[:1].isdigit()]
d = sorted(b - a for a, b in zip(t, t[1:]))
if d:
    print(f"Intervalo entre muestras: medio {1000*sum(d)/len(d):.1f} ms, "
          f"p99 {1000*d[int(0.99*(len(d)-1))]:.1f} ms, máximo {1000*d[-1]:.1f} ms")
PY
echo "tcpdump:"; tail -n 3 "$OUT/${RUN}_tcpdump.txt"
awk -F, 'NR > 1 && ($2 == "base" || $2 == "rec") && $8 > $7 {
  print "AVISO: hubo " $8 - $7 " descartes en " $1 " (" $2 ", " $3 " Mbit/s)" }' "$OUT/${RUN}_fases.csv"
echo "Primeras filas de la traza:"; head -n 3 "$OUT/${RUN}_paquetes.csv"
chown -R "$USUARIO": "$BASE_DIR"
echo "Listo: $OUT"
