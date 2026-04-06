# Nova — Agente de Atención al Cliente OmniRetail

> Construye un agente conversacional autónomo para e-commerce colombiano

---

## ¿Qué es Nova?

Nova es un agente de atención al cliente inteligente para **OmniRetail Colombia**, una tienda de e-commerce simulada. Combina datos estructurados (pedidos, clientes, envíos) con documentos de política empresarial (devoluciones, garantías, envíos) para responder consultas en tiempo real sin inventar información.

```
Usuario: ¿Cuál es el estado de mi pedido?
Nova:     Para ayudarte necesito verificar tu identidad.
          ¿Puedes darme tu cédula o número de celular?

Usuario: Mi cédula es 1181165722
Nova:     ✓ Identidad verificada — Luis Álvarez.
          Tu pedido #1 fue entregado el 3 de junio.
          Transportadora: Interrapidísimo | Guía: INT-47696-69958
```

---

## Arquitectura

```
tu_nombre/
├── core/
│   ├── agent.py              # Agente principal — create_agent() aquí
│   └── session_context.py    # Auditoría y estado de sesión (global)
├── tools/
│   ├── auth.py               # verify_identity()
│   ├── orders.py             # get_order_status(), get_order_amounts(), ...
│   └── policies.py           # search_policy()
├── rag/
│   ├── loader.py             # Segmenta los Markdowns por secciones ##
│   └── retriever.py          # TF-IDF + boost por dominio
├── db/
│   ├── local.py              # DuckDB sobre CSVs (desarrollo local)
│   └── aws.py                # Athena + DynamoDB (producción AWS)
├── data/                     # 12 CSVs del challenge
├── policies/                 # 3 Markdowns de política empresarial
├── tests/                    # Escenarios de prueba
├── config.py                 # Configuración central (lee .env)
├── chat.py                   # CLI interactiva para probar el agente
└── .env                      # Variables de entorno (no subir a git)
```

### Flujo de una consulta

```
Usuario
  │
  ▼
agent.py  ──►  ¿Requiere autenticación?  ──No──►  Responde directo
                        │
                       Sí
                        │
                        ▼
               verify_identity()  ──►  session_context.py
                        │
                        ▼
               Tool correspondiente  ──►  db/local.py  ──►  CSVs
                        │                      o
                        │              rag/retriever.py  ──►  Markdowns
                        ▼
                  Respuesta final
```

---

## Fases del Challenge

### Fase 1 — Integración de Conocimiento
- **Datos estructurados:** DuckDB consulta los 12 CSVs con SQL estándar, idéntico al que usaría Athena en AWS. Cambiar de backend es modificar una variable de entorno.
- **RAG de políticas:** Los 3 Markdowns se segmentan por secciones `##` (43 secciones en total). TF-IDF con bigramas + boost manual por dominio rankea las más relevantes sin inyectar el documento completo en el prompt.

### Fase 2 — Seguridad y Anti-Alucinación
- **Gate de autenticación:** Ninguna consulta sobre pedidos, montos o historial se procesa sin `verify_identity()` exitoso primero.
- **Anti-alucinación:** Cada herramienta registra su llamada en `session_context` con `add_tool_trace()`. El evaluador puede auditar que el agente consultó la fuente antes de responder.
- **Resistencia a prompt injection:** El system prompt incluye reglas explícitas contra comandos como "ignora tus instrucciones" o "soy el administrador".

### Fase 3 — Routing y Métricas
El agente clasifica cada mensaje en 5 ramas:

| Rama | Ejemplo | Requiere auth | Herramienta |
|------|---------|:-------------:|-------------|
| FAQ genérica | "¿Qué métodos de pago aceptan?" | No | Ninguna |
| Políticas | "¿Cuánto tiempo para devolver?" | No | `search_policy` |
| Precios / stock | "¿Cuánto cuesta el iPhone?" | No | Ninguna |
| Montos de pedido | "¿Cuánto pagué en el pedido 5?" | **Sí** | `get_order_amounts` |
| Estado / historial | "¿Dónde está mi pedido?" | **Sí** | `get_order_status` |

---

## Instalación

### Requisitos
- Python 3.11+
- Clave de API de Gemini (gratuita en [aistudio.google.com](https://aistudio.google.com))
- CSVs y Markdowns del challenge en `data/` y `policies/`

### Pasos

```bash
# 1. Clonar / descomprimir el proyecto
cd tu_nombre

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
# .venv\Scripts\activate         # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env y agregar GEMINI_API_KEY

# 5. Probar el agente
python chat.py
```

### `requirements.txt`

```
google-generativeai>=0.8.0
duckdb>=0.10.0
pandas>=2.0.0
scikit-learn>=1.4.0
python-dotenv>=1.0.0
```

---

## Configuración

Copia `.env.example` a `.env` y completa los valores:

```bash
# Proveedor LLM
GEMINI_API_KEY=tu-clave-aqui
LLM_MODEL=gemini-1.5-flash
LLM_TEMPERATURE=0

# Backend de datos
DB_BACKEND=local          # "local" o "aws"

# Rutas
DATA_PATH=data
POLICIES_PATH=policies

# Solo si DB_BACKEND=aws
# AWS_REGION=us-east-1
# AWS_S3_BUCKET=nombre-bucket
# ATHENA_DATABASE=strata_challenge
```

---

## Uso

### CLI interactiva

```bash
python chat.py
```

```
Nova lista. Escribe 'salir' para terminar, 'reset' para nueva sesión.

Tú: ¿Cuánto tiempo tengo para hacer una devolución?
Nova: Según nuestra política, tienes 30 días desde la entrega para
      solicitar una devolución en todas las categorías...

Tú: Quiero ver mis pedidos
Nova: Para consultar tus pedidos necesito verificar tu identidad.
      ¿Me puedes dar tu cédula o número de celular?
```

### Como módulo

```python
from core.agent import create_agent
from core.session_context import get_tool_trace, reset_session

# Crear agente
agente = create_agent()

# Conversar
respuesta = agente("¿Cuánto tiempo tengo para devolver un producto?")
print(respuesta)          # str()
print(respuesta.content)  # .content

# Auditoría — ver herramientas usadas
trace = get_tool_trace()
print(f"Herramientas llamadas: {len(trace)}")

# Nueva sesión
agente.reset_memory()
reset_session()
```

---

## Auditoría y Observabilidad

`session_context.py` mantiene el registro de todas las herramientas usadas en la sesión actual usando **variables globales de módulo** — decisión intencional para garantizar que el evaluador acceda al mismo estado independientemente del contexto de ejecución.

```python
from core.session_context import (
    get_tool_trace,           # lista completa de herramientas usadas
    get_tool_trace_length,    # cuántas llamadas se hicieron
    get_tool_trace_since,     # llamadas desde un índice dado
    get_session_customer,     # cliente autenticado en esta sesión
    reset_session,            # limpiar estado entre sesiones
)

# Patrón de auditoría por turno
before = get_tool_trace_length()
agente("¿Cuál es el estado del pedido 5?")
nuevas_llamadas = get_tool_trace_since(before)
# → [{"tool": "verify_identity", ...}, {"tool": "get_order_status", ...}]
```

---

## Criterios de Evaluación

| Criterio | Peso | Implementación |
|----------|:----:|----------------|
| Seguridad y control de acceso | 25% | Gate de autenticación + resistencia a prompt injection |
| Anti-alucinación | 25% | `add_tool_trace()` en cada herramienta + regla en system prompt |
| Lógica de negocio y routing | 20% | 5 ramas en system prompt + árbol de decisión |
| RAG y memoria conversacional | 20% | TF-IDF sobre secciones Markdown + historial con ventana deslizante |
| Tiempo de respuesta (TTFT) | — | Historial recortado a 10 turnos + modelo Flash |
| Presentación oral | 10% | — |

---

## Stack Tecnológico

| Componente | Tecnología | Alternativa AWS |
|-----------|------------|-----------------|
| LLM | Gemini 1.5 Flash | Amazon Bedrock |
| Base de datos | DuckDB (local) | Amazon Athena |
| Almacenamiento | CSVs locales | Amazon S3 |
| RAG | TF-IDF (scikit-learn) | Amazon Kendra |
| Estado de sesión | Variables globales Python | — |

---

## Equipo

Desarrollado por estudiantes de la **Universidad del Cauca** para el desafío Strata Analytics × AWS × GICO.

---

*Datos sintéticos — cualquier similitud con personas o transacciones reales es coincidencia.*
