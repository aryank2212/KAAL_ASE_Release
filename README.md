# KAAL: The All Seeing Eye (ASE) - Intelligent OSINT Investigator

Hey everyone. This is KAAL (ASE), an intelligent OSINT investigation tool that combines traditional web scraping and social media discovery with an ML-guided continuous loop. I built this to automate the tedious parts of OSINT gathering and help filter out the noise.

Basically, you feed it a name, a little context, and some starting links, and the script handles the rest. It uses a local LLM to judge the relevance of the scraped data so it doesn't get distracted by random Wikipedia articles or historical fluff. 

## Prerequisites & Installation

To run this, you'll need a few things installed on your system:

1. **Python 3.10+**
2. **cURL**: Make sure you have `curl` installed and accessible in your system PATH (used for fetching pages safely).
3. **Ollama**: You need this running locally to power the LLM analysis.
   - Download it from [ollama.com](https://ollama.com/)
   - Once installed, pull the models you want to use. I recommend `gemma4:latest` or `gemma2:2b`.
   - Run: `ollama run gemma4:latest` (or whichever model you choose) so it's active on port `11434`.

### Setup

Clone the repo and install the required Python packages:

```bash
git clone https://github.com/yourusername/KAAL-ASE.git
cd KAAL-ASE
pip install -r requirements.txt
```

## How to Use

First, you need to spin up the backend API that handles the heavy lifting. I've included an `infra` setup for this. 
*(Note: A huge shoutout to the original Infra structure—I built and tweaked it a bit to make it fully compatible with KAAL (ASE)).*

You can start the backend using Docker or directly with uvicorn (if you're just testing):
```bash
python -m uvicorn services.api.app.main:app --reload --host 0.0.0.0 --port 8000
```

Once the API and Ollama are both running, just launch the main script:
```bash
python intelligent_recon.py
```

It will prompt you for the target's details:
- **Full name**: The person you are looking for.
- **Background context**: Quick context (e.g., "19 yr old student in Delhi").
- **Known links**: Drop their Instagram, YouTube, or email here. 
- **Phrase / quote**: Anything specific you want to search.

Let it run for the duration you set, and it will output a comprehensive intelligence report in the `reports/` folder.

## Credits & Acknowledgements

This project relies on some awesome open-source tools from the community:
- **Ollama**: For making local LLM execution painless.
- **FastAPI / Uvicorn**: Powering the backend API seamlessly.
- **Maigret**: Huge credit to the Maigret project for the underlying username scraping logic.
- **cURL**: For reliable and simple web requests.

Feel free to fork, mess around with the prompts, and submit PRs. Enjoy!
