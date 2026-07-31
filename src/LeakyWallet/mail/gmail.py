import httpx

GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"


async def get_profile_email(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GMAIL_PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        payload = response.json()
    return str(payload["emailAddress"])
