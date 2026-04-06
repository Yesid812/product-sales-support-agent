import os 
from pathlib  import Path 
from dotenv import load_dotenv

#Load variables from .env file whether it exists
load_dotenv()

# Project root - file's folder
BASER_DIR = Path(__file__).parent

class SettingClass:


    #Api-key of the used LLLM in my case GPT or Claude idk yet
    API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Model name of the used LLM. Use a Gemini model compatible with the current API.
    # Cambia este valor en .env si necesitas otro modelo.
    MODEL_NAME = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")

    # Backend data section
    # For the local development I use  DuckDB
    # For the production I'll use Athena + DynamoDB for caching
    db_backend = os.getenv("DB_BACKEND", "duckdb")

    # Routes

    # Load all csv files
    data_path: Path = BASER_DIR / os.getenv("DATA_PATH", "data")

    # Load md files containing policies 
    policies_path: Path = BASER_DIR / os.getenv("POLICIES_PATH", "policies")

    # AWS S3 bucket name for storing data and policies in production
    # Only if db_backend is set to "aws"
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    aws_bucket: str = os.getenv("AWS_BUCKET", "")
    athena_database: str = os.getenv("ATHENA_DATABASE", "strata_challenge")
    athena_output: str = os.getenv("ATHENA_OUTPUT_LOCATION", "")


    # Agent settings

    # Max time of the agent - max 10s to respond to the user query, otherwise penalized 
    max_response_seconds: int = int(os.getenv("MAX_RESPONSE_SECONDS", "8"))

    # Model's temperature - how creative the model's responses will be
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0"))

    def validate(self) -> None:
        """" Verify that all required settings are set and valid. """
        """ Call this for early verification errors before starting the app."""
        """ It will raise a clear error """

        if not self.API_KEY:
            raise ValueError("API_KEY is not set in .env file add it on the .env " \
            "file or set it as an environment variable")
        

        if self.llm_provider == "gemini" and not self.API_KEY:
            raise ValueError("GEMINI_API_KEY no está configurada.")
        
        # This is for the local dev
        if not self.data_path.exists():
            raise ValueError(f"DATA_PATH {self.data_path} does not exist. "\
            "Please add it to the .env file or set it as an environment variable")

        if not self.policies_path.exists():
            raise ValueError(f"POLICIES_PATH {self.policies_path} does not exist. "\
            "Please add it to the .env file or set it as an environment variable")
        
# Only this instance to import all project settings   
settings = SettingClass()