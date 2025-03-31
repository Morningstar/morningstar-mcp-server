from mcp.server.fastmcp import FastMCP
import httpx
import logging
from dotenv import load_dotenv
import os

load_dotenv()

datapoint_tool_url = os.environ["DATAPOINT_TOOL_URL"]
retrieval_tool_url = os.environ["RETRIEVAL_TOOL_URL"]

# Configure logging
logging.basicConfig(
    level=logging.DEBUG
)  # Move this to INFO as the application becomes more stable
logger = logging.getLogger(__name__)

# By restricting the logging level of these libraries, we can reduce the noise in the logs.
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("mcp").setLevel(logging.ERROR)
logging.getLogger("mcp").setLevel(logging.ERROR)
logging.getLogger("openai").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("sse_starlette").setLevel(logging.ERROR)


# Initialize FastMCP server
mcp = FastMCP("Morningstar MCP Server")


@mcp.tool(
    name="morningstar-datapoint-tool",
    description="use this tool to fetch latest values for Morningstar datapoints such as market capitalization, ratings, fair value ratio, fair value estimate, last closing price, total return, economic moat, earnings per share (EPS), net asset value (NAV), fund size, sector, domicile, primary share and more. Use this tool when the question is just a simple datapoint information look up for a security such as a stock or fund.",
)
async def morningstar_datapoints_tool(authorization_token: str, question: str) -> str:
    """Returns Morningstar datapoint information for a given question
    See https://developer.morningstar.com/direct-web-services/documentation/documentation/get-started/authentication
    for authentication details.
    Args:
        authorization_token (str): The authorization token for the Morningstar API.
        question (str): The question that can be answered by Morningstar Datapoint Tool.
    Returns:
        str: The answer from the Morningstar Datapoint Tool.
    """

    logger.info(f"Calling Morningstar Datapoint Tool with question: {question}")

    headers = {
        "Authorization": f"Bearer {authorization_token}",
    }

    body = {
        "tool_input": {"question": question},
        "additional_kwargs": {
            "datapoint": {"enable": True},
            "filters": {
                "domicile": ["United States"],
                "exchanges": [
                    "New York Stock Exchange, Inc.",
                    "Nasdaq - All Markets",
                ],
            },
            "screener": {"enable": False, "search_type": "sql_agent"},
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=datapoint_tool_url, headers=headers, json=body
            )
            response.raise_for_status()  # Raise an error for bad status codes
            logger.info(f"Response from Morningstar Datapoint Tool: {response.json()}")
            return response.json()["answer"]
    except httpx.HTTPStatusError as http_err:
        logger.exception(
            f"HTTP error occurred: {http_err.response.status_code} - {http_err.response.text}"
        )
        return f"Error: {str(http_err)}"
    except httpx.RequestError as req_err:
        logger.exception(f"Error calling Morningstar Datapoint Tool: {str(req_err)}")
        return f"Error: {str(req_err)}"


@mcp.tool(
    name="morningstar-articles-tool",
    description="use this tool for getting answers for questions about finance, investing, sustainable investing, investment strategies, portfolio and retirement. It is a reliable resource for obtaining Morningstar's opinion, research, and analysis from Morningstar's Editorial content, methodologies and Thematic research. This tool relies solely on reliable research conducted by Morningstar for all of the information provided. This tool is not intended to provide factual information regarding a stock or fund's rating, price, fair value, or performance.",
)
async def morningstar_articles_tool(authorization_token: str, question: str) -> str:
    """Answers a given question from Morningstar articles
    See https://developer.morningstar.com/direct-web-services/documentation/documentation/get-started/authentication
    for authentication details.
    Args:
        authorization_token (str): The authorization token for the Morningstar API.
        question (str): The question that can be answered using the Morningstar Articles Tool.
    """

    logger.info("Calling IEP Retrieval Tool")
    logger.debug(f"Question: {question}")

    headers = {
        "Authorization": f"Bearer {authorization_token}",
    }

    body = {
        "tool_input": {"question": question},
        "additional_kwargs": {
            "prompt": "Answer the question: {question}, using the following summaries: {summaries}",
            "corpus_configs": [
                {
                    "corpus_slug": "research",
                    "retrieval_type": "hybrid",
                    "search_args": {
                        "alpha": 0.5,
                        "hybrid_search_kwargs": {
                            "fusion_type": "relativeScoreFusion",
                            "properties": ["content"],
                        },
                    },
                    "weaviate_class_name": "Articles_v2",
                }
            ],
            "use_structured_outputs": True,
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=retrieval_tool_url, headers=headers, json=body
            )
            response.raise_for_status()  # Raise an error for bad status codes
            logger.info("Successfully got response from IEP Retrieval QA Tool")
            logger.debug(f"Response from IEP Retrieval QA Tool: {response.json()}")
            return response.json()["answer"]  # Return the tool output from the response
    except httpx.HTTPStatusError as http_err:
        logger.exception(
            f"HTTP error occurred: {http_err.response.status_code} - {http_err.response.text}"
        )
        return f"HTTP Error: {http_err.response.status_code} - {http_err.response.text}"
    except httpx.RequestError as req_err:
        logger.exception(f"Network error occurred: {str(req_err)}")
        return f"Network Error: {str(req_err)}"


if __name__ == "__main__":
    mcp.run(
        transport="stdio",  # sse is the other option, at which point it listens on port 8000 by default
    )  # default port 8000
