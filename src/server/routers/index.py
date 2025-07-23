"""Module defining the FastAPI router for the home page of the application."""

from fastapi import APIRouter, Depends, Request, Form, HTTPException

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from autotiktokenizer import AutoTikTokenizer
import tiktoken
from typing import Optional

from gitingest.utils.compat_typing import Annotated
from server.models import QueryForm
from server.query_processor import process_query
from server.server_config import EXAMPLE_REPOS, templates
from server.server_utils import limiter
from pydantic import BaseModel, Field


router = APIRouter()

templates = Jinja2Templates(directory="server/templates")

SUPPORTED_MODELS = {
    'GPT-2 (OpenAI)': 'openai-community/gpt2',
    'GPT-3 (OpenAI)': 'openai-community/gpt2',
    'GPT-3.5 (OpenAI)': 'openai-community/gpt2',
    'GPT-3.5-turbo (OpenAI)': 'openai-community/gpt2',
    'GPT-4 (OpenAI)': 'openai-community/gpt2',
    'Claude (approximate, uses GPT-2)': 'openai-community/gpt2',
    'Gemini (approximate, uses T5)': 't5-base',
    'Llama-2 (Meta)': 'meta-llama/Llama-2-7b-hf',
    'Llama-3 (Meta)': 'meta-llama/Meta-Llama-3-8B',
    'Mistral-7B (MistralAI)': 'mistralai/Mistral-7B-v0.1',
    'Mixtral-8x7B (MistralAI)': 'mistralai/Mixtral-8x7B-v0.1',
    'Phi-3-mini (Microsoft)': 'microsoft/phi-3-mini-4k-instruct',
    'Gemma-2B (Google)': 'google/gemma-2b',
    'Qwen2-7B (Alibaba)': 'Qwen/Qwen2-7B',
    'Yi-34B (01.AI)': '01-ai/Yi-34B-Chat',
    'Falcon-7B (TII)': 'tiiuae/falcon-7b',
    'MPT-7B (MosaicML)': 'mosaicml/mpt-7b',
    'Baichuan-7B (Baichuan)': 'baichuan-inc/Baichuan-7B',
    'XLM-RoBERTa-base (Facebook)': 'xlm-roberta-base',
    'RoBERTa-base (Facebook)': 'roberta-base',
    'DistilBERT-base-uncased': 'distilbert-base-uncased',
    'GPT-Neo-1.3B (EleutherAI)': 'EleutherAI/gpt-neo-1.3B',
    'GPT-J-6B (EleutherAI)': 'EleutherAI/gpt-j-6B',
    'GPT-Bloom-560m (BigScience)': 'bigscience/bloom-560m',
    'BERT-base-uncased': 'bert-base-uncased',
    'T5-base': 't5-base',
}
# Note: Gemini and Claude use approximate tokenizers (T5 and GPT-2, respectively) as no official public tokenizers exist for these models.

def get_tokenizer(model_id):
    return AutoTikTokenizer.from_pretrained(model_id)

def count_tokens(input_text, model_id):
    if model_id == 'openai-community/gpt2':
        # Use tiktoken for OpenAI models
        enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(enc.encode(input_text))
    else:
        tokenizer = AutoTikTokenizer.from_pretrained(model_id)
        return len(tokenizer.encode(input_text))

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request) -> HTMLResponse:
    """Render the home page with example repositories and default parameters.

    This endpoint serves the home page of the application, rendering the ``index.jinja`` template
    and providing it with a list of example repositories and default file size values.

    Parameters
    ----------
    request : Request
        The incoming request object, which provides context for rendering the response.

    Returns
    -------
    HTMLResponse
        An HTML response containing the rendered home page template, with example repositories
        and other default parameters such as file size.

    """
    return templates.TemplateResponse(
        "index.jinja",
        {
            "request": request,
            "examples": EXAMPLE_REPOS,
            "default_max_file_size": 243,
        },
    )


@router.post("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def index_post(request: Request, form: Annotated[QueryForm, Depends(QueryForm.as_form)]) -> HTMLResponse:
    """Process the form submission with user input for query parameters.

    This endpoint handles POST requests from the home page form. It processes the user-submitted
    input (e.g., text, file size, pattern type) and invokes the ``process_query`` function to handle
    the query logic, returning the result as an HTML response.

    Parameters
    ----------
    request : Request
        The incoming request object, which provides context for rendering the response.
    form : Annotated[QueryForm, Depends(QueryForm.as_form)]
        The form data submitted by the user.

    Returns
    -------
    HTMLResponse
        An HTML response containing the results of processing the form input and query logic,
        which will be rendered and returned to the user.

    """
    resolved_token = form.token if form.token else None
    return await process_query(
        request,
        input_text=form.input_text,
        slider_position=form.max_file_size,
        pattern_type=form.pattern_type,
        pattern=form.pattern,
        is_index=True,
        token=resolved_token,
    )


class TokenCountRequest(BaseModel):
    input_text: str = Field(..., description="The text to count tokens for")
    model_id: str = Field(default="openai-community/gpt2", description="The model ID to use for tokenization")

class TokenCountResponse(BaseModel):
    token_count: int = Field(..., description="Number of tokens in the input text")
    model_id: str = Field(..., description="Model ID used for tokenization")
    character_count: int = Field(..., description="Number of characters in the input text")

@router.post("/api/tokencount", response_model=TokenCountResponse)
async def api_token_count(
    request: Optional[TokenCountRequest] = None,
    input_text: str = Form(None),
    model_id: str = Form(default="openai-community/gpt2"),
):
    """
    Count tokens in the provided text using the specified model's tokenizer.
    Accepts both JSON and form data.
    """
    # If JSON body was provided, use that
    if request:
        text = request.input_text
        model = request.model_id
    # Otherwise use form data
    else:
        text = input_text
        model = model_id

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty")
    
    if model not in SUPPORTED_MODELS.values():
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported model ID. Must be one of: {', '.join(SUPPORTED_MODELS.values())}"
        )
    
    try:
        token_count = count_tokens(text, model)
        return TokenCountResponse(
            token_count=token_count,
            model_id=model,
            character_count=len(text)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tokencount", response_class=HTMLResponse)
async def tokencount_ui(request: Request):
    return templates.TemplateResponse(
        "tokencount.jinja",
        {"request": request, "supported_models": SUPPORTED_MODELS, "input_text": "", "model_id": "openai-community/gpt2", "result": None, "error": None}
    )

@router.post("/tokencount", response_class=HTMLResponse)
async def tokencount_post(request: Request, input_text: str = Form(...), model_id: str = Form("openai-community/gpt2")):
    error = None
    result = None
    if not input_text or not input_text.strip():
        error = "Input text cannot be empty."
    elif model_id not in SUPPORTED_MODELS.values():
        error = f"Unsupported model ID. Must be one of: {', '.join(SUPPORTED_MODELS.values())}"
    else:
        try:
            token_count = count_tokens(input_text, model_id)
            result = {
                "token_count": token_count,
                "model_id": model_id,
                "character_count": len(input_text)
            }
        except Exception as e:
            error = str(e)
    return templates.TemplateResponse(
        "tokencount.jinja",
        {
            "request": request,
            "supported_models": SUPPORTED_MODELS,
            "input_text": input_text,
            "model_id": model_id,
            "result": result,
            "error": error
        }
    )
