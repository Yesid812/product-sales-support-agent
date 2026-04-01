from config import settings
from core.agent import Agent


def main() -> None:
    try:
        settings.validate()
    except Exception as exc:
        print(f"Error de configuración: {exc}")
        return

    agent = Agent.create_agent()
    print("Agente de soporte listo. Escribe 'salir' para terminar.")

    while True:
        mensaje = input("Usuario: ").strip()
        if mensaje.lower() in {"salir", "exit", "quit"}:
            print("Agente: Hasta luego.")
            break

        respuesta = agent.respond(mensaje)
        print(f"Agente: {respuesta}\n")


if __name__ == "__main__":
    main()
