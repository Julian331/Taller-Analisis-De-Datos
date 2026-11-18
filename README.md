# Predicción de congestión en un enlace: captura de tráfico y selección de modelo

Laboratorio de Inteligencia Artificial (Universidad Sergio Arboleda, 2026-2).
El informe está en `informe/informe.pdf`.

## Estructura

```
captura/corrida.sh          captura de una corrida en A (tcpdump + muestreo de la cola + fases de iperf3)
captura/todas.log           salida de la captura de las 6 corridas
captura/qdisc_original.txt  cola original de eth0 en A, antes de poner la TBF
datos/c01 … c06/            por corrida:
    cXX.pcap                  traza capturada con tcpdump (se abre con Wireshark)
    cXX_paquetes.csv          la misma traza en CSV: tiempo y longitud de cada trama
    cXX_cola.log              registro de la cola (tiempo + JSON de `tc -j -s` cada 0,05 s)
    cXX_faseNN.json           resultado de iperf3 de cada fase (con la salida del servidor)
    cXX_fases.csv             hora de inicio/fin y descartes de cada fase
    cXX_plan.txt              calendario de la corrida (etiqueta, tasa, duración)
    cXX_tc_inicio/fin.txt, cXX_tcpdump.txt   estado de la cola y estadísticas de captura
datos/prueba/               piloto (no entra al análisis)
datos/fallidas/             primera c06, interrumpida por error (no entra al análisis)
analisis/                   código del análisis (ver abajo)
resultados/ventanas.csv     CSV de ventanas de 0,1 s (las 6 corridas, con la marca de validez)
resultados/                 selección en validación, métricas de prueba, umbrales, predicciones
informe/                    informe.pdf, informe.tex y figuras/
```

Corridas 1–3: entrenamiento; 4: validación; 5–6: prueba.

## Montaje de la captura

- **A (emisor):** Ubuntu 24.04 en WSL2, con iperf3 3.22 y tcpdump. Cola en la salida:
  `tc qdisc replace dev eth0 root handle 10: tbf rate 10mbit burst 16kb limit 32kb`.
- **B (receptor):** Windows anfitrión, con `iperf3.exe -s --logfile …` (iperf3 3.22).
- **Captura:** cada corrida se lanza con `bash captura/corrida.sh cXX eth0`, o las seis con
  `bash captura/corrida.sh todas eth0`, como root en A. El calendario de cada corrida se
  sortea con una semilla fija, así que siempre sale igual.

## Reproducir el análisis

Requisitos (versiones con las que se obtuvieron los resultados): Python 3.13, numpy 2.5.3,
pandas 3.0.5, scikit-learn 1.9.1, matplotlib 3.11.2.

```bash
cd analisis
python3 seleccion.py   # ventanas + selección de hiperparámetros y umbral en validación (c04)
python3 prueba.py      # evaluación única en prueba (c05–c06)
python3 figuras.py     # figuras del informe
```

En Linux o WSL basta con `bash analisis/ejecutar.sh`. Si los datos están en otra carpeta,
indícala con la variable de entorno `DATOS_LAB`.

| Archivo | Qué hace |
|---|---|
| `cargar.py` | lee el registro de cola, la traza en CSV y las fases |
| `ventanas.py` | ventanas de 0,1 s: r_k, n_k, d_k, overlimits y validez (sin cruzar pausas del muestreo) |
| `modelos.py` | conjunto de datos, candidatos (regresión lineal, árbol, MLP), umbral por F1 y métricas |
| `seleccion.py` | entrena con c01–c03 y elige el hiperparámetro y el umbral en c04 |
| `prueba.py` | evalúa una sola vez en c05–c06 |
| `figuras.py` | figuras en PDF para el informe |

## Compilar el informe

```bash
cd informe && pdflatex informe.tex && pdflatex informe.tex
```

Si en `informe/` hay un archivo `logo_usa.png`, la portada lo incluye.
