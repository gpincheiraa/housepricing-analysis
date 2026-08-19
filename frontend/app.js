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

  result.textContent = "Autenticando con Google...";

  try {
    // 1. Validar identidad contra nuestro BFF
    const bffResponse = await fetch(`${BFF_URL}/me`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${response.credential}`,
      },
    });

    const userData = await bffResponse.json();

    if (!bffResponse.ok) {
      throw new Error(
        userData.detail || "No fue posible autenticar al usuario",
      );
    }

    result.textContent =
      `Usuario autenticado:\n\n` +
      `${JSON.stringify(userData, null, 2)}\n\n` +
      `Generando conexión con Mercado Libre...`;

    // 2. Pedir al BFF la URL de autorización de Mercado Libre
    const mlResponse = await fetch(
      `${BFF_URL}/oauth/mercadolibre`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${response.credential}`,
        },
      },
    );

    const mlData = await mlResponse.json();

    if (!mlResponse.ok) {
      throw new Error(
        mlData.detail ||
        "No fue posible iniciar la autenticación con Mercado Libre",
      );
    }

    // 3. Mostrar información de prueba
    result.textContent =
      `Usuario autenticado:\n\n` +
      `${JSON.stringify(userData, null, 2)}\n\n` +
      `Mercado Libre:\n\n` +
      `${JSON.stringify(
        {
          google_user: mlData.google_user,
          authorization_url: mlData.authorization_url,
        },
        null,
        2,
      )}`;

    // 4. Abrir Mercado Libre
    window.location.href = mlData.authorization_url;

  } catch (error) {
    console.error(error);

    result.textContent =
      `Error:\n\n${error.message}`;
  }
}
