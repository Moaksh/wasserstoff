import asyncio
import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

from browser_use import Agent, BrowserConfig
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContextConfig

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
	raise ValueError('GEMINI_API_KEY is not set')

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', api_key=SecretStr(api_key))

browser = Browser(
	config=BrowserConfig(
		new_context_config=BrowserContextConfig(
			viewport_expansion=0,
		),
        chrome_instance_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
		
	)
)


async def run_search():
	agent = Agent(
		task='Go to Linkdn and scrape profiles of people with the title "Software Engineer"',
		llm=llm,
		max_actions_per_step=4,
		browser=browser,
	)

	await agent.run(max_steps=25)


if __name__ == '__main__':
	asyncio.run(run_search())