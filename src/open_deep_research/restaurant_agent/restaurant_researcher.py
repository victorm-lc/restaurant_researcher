import asyncio
import json
from typing import TypedDict, Dict, List

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from pydantic import BaseModel, Field
from open_deep_research.deep_researcher import deep_researcher

REQUEST = """
I have rented a new storefront at Fisherman's Wharf in San Francisco to open a restaurant. Please 
help me design a strategy and theme to operate the new restaurant, including but not limited to the 
cuisine and menu to offer, staff recruitment requirements including salary, and marketing and 
promotional strategies. Provide one best option rather than multiple choices. Based on the option, generate:

Write a comprehensive report with an introduction and conclusion.

Also generate a FAQ for diners about the details of the restaurant.
"""

class MenuItemWithImage(BaseModel):
    name: str
    price: float
    recipe: str
    image: str


class MenuWithImages(BaseModel):
    items: List[MenuItemWithImage]


class AgentState(TypedDict):
    # The user's request
    request: str
    # A URL to an image of a blank storefront
    storefront_url: str
    # Comprehensive report
    restaurant_description: str
    # Menu items
    menu: MenuWithImages
    # Rendered storefront
    storefront_rendering: str


async def generate_image_for_prompt(prompt: str) -> str:
    tool = {"type": "image_generation"}
    model = ChatOpenAI(model="gpt-5-mini", output_version="responses/v1").bind_tools([tool])
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"Generate the image this prompt specifies: {prompt}"),
    ])
    chain = prompt | model
    result = await chain.ainvoke({})
    return result.content[1]["result"]


async def generate_storefront(
        state: AgentState):
    """
    Use the LLM to create a prompt for the image generator.
    """
    restaurant_description = state["restaurant_description"]
    storefront_url = state["storefront_url"]
    message = HumanMessage(content=[
        {
            "type": "text",
            "text": f"Generate a detailed prompt to redraw how the attached vacant storefront would best look like "
                    f"if it were a restaurant with the following description: {restaurant_description}"
        },
        {
            "type": "image",
            "source_type": "url",
            "url": storefront_url,
        }
    ])
    model = init_chat_model("gpt-5-mini", model_provider="openai")
    response = model.invoke([message]).content
    rendering = await generate_image_for_prompt(response)
    return {
        "storefront_rendering": rendering
    }




# LLM out models for menu items
class MenuItem(BaseModel):
    name: str = Field(description="The name of the menu item.")
    price: float = Field(description="The price of the menu item.")
    recipe: str = Field(description="The recipe of the menu item.")


class Menu(BaseModel):
    items: List[MenuItem] = Field(description="The menu items.")


async def generate_image_for_menu_item(menu_item: MenuItem) -> MenuItemWithImage:
    """
    Use the LLM to create a prompt for the image generator.
    """
    message = HumanMessage(content=f"""
    Given the name and recipe for this menu item, write a prompt to generate an appealing accompanying image:\n
    Name: {menu_item.name}\n
    Recipe: {menu_item.recipe}
    """)
    model = init_chat_model("gpt-5-mini", model_provider="openai")
    response = await model.ainvoke([message])
    response = response.content
    image = await generate_image_for_prompt(response)
    return MenuItemWithImage(
        **menu_item.model_dump(),
        image=image,
    )


async def generate_menu(state: AgentState):
    model = init_chat_model("gpt-5-mini", model_provider="openai")
    model = model.with_structured_output(Menu)
    message = HumanMessage(content=f"""
         Based on this restaurant description, create a sample menu with a handful of dishes,
         including price and recipe with preparation methods: {state['restaurant_description']}
    """)
    response: Menu = model.invoke([message])
    futures = [generate_image_for_menu_item(i) for i in response.items]
    menu_items_with_images = await asyncio.gather(*futures)
    return {"menu": MenuWithImages(items=menu_items_with_images)}


async def generate_restaurant_description(state: AgentState) -> Dict:
    """Takes a really long time"""
    result = await deep_researcher.ainvoke({
        "messages": [HumanMessage(content=state["request"])]
    })
    return {
        "restaurant_description": result["final_report"]
    }
    # with open("example2.txt", "r") as f:
    #     content = f.read()
    # return {"restaurant_description": content}



builder = StateGraph(AgentState)
builder.add_node("restaurant_description", generate_restaurant_description)
builder.add_node("menu", generate_menu)
builder.add_node("storefront", generate_storefront)

builder.add_edge(START, "restaurant_description")
builder.add_edge("restaurant_description", "menu")
builder.add_edge("menu", "storefront")
builder.add_edge("storefront", END)

restaurant_researcher = builder.compile()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    state = AgentState(
        request=REQUEST,
        storefront_url="https://static01.nyt.com/images/2017/06/01/fashion/01BLEEKER/01BLEEKER-superJumbo.jpg?quality=75&auto=webp",
    )
    result = asyncio.run(restaurant_researcher.ainvoke(state))
    with open('report.md', 'w') as f:
        f.write(result["restaurant_description"])
    with open('menu2.json', 'w') as f:
        json.dump(result["menu"].model_dump(mode='json'), f)
    with open('storefront.txt', 'w') as f:
        f.write(result['storefront_rendering'])