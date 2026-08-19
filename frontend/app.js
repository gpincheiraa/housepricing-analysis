const GOOGLE_CLIENT_ID = "366674000591-k5n9g6vo12vrk40egcmn1ht3cnvlrciv.apps.googleusercontent.com";

const BFF_URL =
  "https://housepricing-web-bff-vyghkhukra-tl.a.run.app";

window.onload = () => {
  google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: handleGoogleCredential,
  });

  google.accounts.id.renderButton(
    document.getElementById("google-login"),
    {
      theme: "outline",
      size: "large",
    },
  );
};

async function handleGoogleCredential(response) {
  const result = document.getElementById("result");

  result.textContent = "Autenticando...";

  try {
    const responseBff = await fetch(`${BFF_URL}/me`, {
      headers: {
        Authorization: `Bearer ${response.credential}`,
      },
    });

    const data = await responseBff.json();

    result.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    result.textContent = String(error);
  }
}