# chat.py — prueba interactiva del agente
from core.agent import create_agent
from core.session_context import reset_session

agente = create_agent()
print("Nova lista. Escribe 'salir' para terminar, 'reset' para nueva sesión.\n")

while True:
    try:
        user = input("Tú: ").strip()
    except (EOFError, KeyboardInterrupt):
        break

    if not user:
        continue
    if user.lower() == "salir":
        break
    if user.lower() == "reset":
        agente.reset_memory()
        print("Nova: Sesión reiniciada.\n")
        continue

    respuesta = agente(user)
    print(f"Nova: {respuesta}\n")
reset_session()