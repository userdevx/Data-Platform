use matrix_sdk::{
    ruma::api::client::{
        account::register::v3::{
            Request as RegistrationRequest,
            Response as RegistrationResponse,
        },
        uiaa::{
            AuthData,
            RegistrationToken,
        },
    },
    Client,
};
use serde::{Deserialize, Serialize};
use std::fs;
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::process::Command;


#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MessagingStatusResponse {
    pub status: String,
    pub available: bool,
    pub server_name: String,
    pub homeserver_url: String,
    pub detail: String,
}


#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MessagingRegisterAccountRequest {
    pub user_id: String,
    pub username: String,
    pub password: String,
}


#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MessagingRegisterAccountResponse {
    pub status: String,
    pub user_id: String,
    pub messaging_user_id: String,
    pub device_id: Option<String>,
}


fn messaging_homeserver_url() -> String {
    std::env::var("MESSAGING_MATRIX_BASE_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:8008".to_string())
}


fn messaging_server_name() -> String {
    std::env::var("MESSAGING_MATRIX_SERVER_NAME")
        .unwrap_or_else(|_| "dataworc.com".to_string())
}


fn messaging_registration_token_path() -> String {
    std::env::var(
        "MESSAGING_REGISTRATION_TOKEN_FILE"
    )
    .unwrap_or_else(
        |_| "/etc/tuwunel/.reg_token".to_string()
    )
}


fn read_registration_token() -> Result<String, String> {
    let path = messaging_registration_token_path();

    let token = fs::read_to_string(&path)
        .map_err(|error| {
            format!(
                "Messaging registration credential could not be read: {error}"
            )
        })?
        .trim()
        .to_string();

    if token.is_empty() {
        return Err(
            "Messaging registration credential is empty."
                .to_string()
        );
    }

    Ok(token)
}


async fn build_messaging_client() -> Result<Client, String> {
    let homeserver_url = messaging_homeserver_url();

    Client::builder()
        .homeserver_url(&homeserver_url)
        .disable_well_known_lookup(true)
        .build()
        .await
        .map_err(|error| {
            format!(
                "Messaging client could not be created: {error}"
            )
        })
}


fn clean_username(
    username: &str,
) -> Result<String, String> {
    let clean = username.trim();

    if clean.is_empty() {
        return Err(
            "Messaging username is required."
                .to_string()
        );
    }

    if clean.starts_with('@')
        || clean.contains(':')
    {
        return Err(
            "Messaging username must be a local username, not a full Matrix ID."
                .to_string()
        );
    }

    Ok(clean.to_string())
}


fn clean_user_id(
    user_id: &str,
) -> Result<String, String> {
    let clean = user_id.trim();

    if clean.is_empty() {
        return Err(
            "DataWorc user_id is required."
                .to_string()
        );
    }

    if !clean.starts_with("user_") {
        return Err(
            "DataWorc user_id must use the internal user_ identifier format."
                .to_string()
        );
    }

    Ok(clean.to_string())
}


fn clean_password(
    password: &str,
) -> Result<String, String> {
    if password.is_empty() {
        return Err(
            "Messaging password is required."
                .to_string()
        );
    }

    Ok(password.to_string())
}


fn base_registration_request(
    username: &str,
    password: &str,
) -> RegistrationRequest {
    let mut request =
        RegistrationRequest::new();

    request.username =
        Some(username.to_string());

    request.password =
        Some(password.to_string());

    request
}


async fn register_with_token(
    client: &Client,
    username: &str,
    password: &str,
    token: &str,
) -> Result<RegistrationResponse, String> {
    /*
     * Matrix registration uses UIAA.
     *
     * First request:
     *     no auth
     *
     * Expected result:
     *     UIAA challenge containing a session ID
     *
     * Second request:
     *     same username/password
     *     registration-token auth
     *     same UIAA session
     */

    let first_request =
        base_registration_request(
            username,
            password,
        );

    let first_result = client
        .matrix_auth()
        .register(first_request)
        .await;

    let error = match first_result {
        Ok(response) => {
            /*
             * A server may allow registration without
             * UIAA. In that case registration is already
             * complete.
             */
            return Ok(response);
        }

        Err(error) => error,
    };

    let uiaa_info = error
        .as_uiaa_response()
        .ok_or_else(|| {
            format!(
                "Messaging registration did not return a UIAA challenge: {error}"
            )
        })?;

    let session = uiaa_info
        .session
        .clone()
        .ok_or_else(|| {
            "Messaging registration UIAA challenge did not contain a session."
                .to_string()
        })?;

    let mut token_auth =
        RegistrationToken::new(
            token.to_string()
        );

    token_auth.session =
        Some(session);

    let mut second_request =
        base_registration_request(
            username,
            password,
        );

    second_request.auth =
        Some(
            AuthData::RegistrationToken(
                token_auth
            )
        );

    client
        .matrix_auth()
        .register(second_request)
        .await
        .map_err(|error| {
            format!(
                "Messaging account registration failed: {error}"
            )
        })
}


#[tauri::command]
pub async fn get_messaging_status(
) -> Result<MessagingStatusResponse, String> {
    let homeserver_url =
        messaging_homeserver_url();

    let server_name =
        messaging_server_name();

    let client =
        build_messaging_client().await?;

    match client.supported_versions().await {
        Ok(_) => Ok(
            MessagingStatusResponse {
                status: "ok".to_string(),
                available: true,
                server_name,
                homeserver_url,
                detail:
                    "Messaging service is available."
                        .to_string(),
            },
        ),

        Err(error) => Ok(
            MessagingStatusResponse {
                status:
                    "unavailable".to_string(),
                available: false,
                server_name,
                homeserver_url,
                detail: format!(
                    "Messaging service check failed: {error}"
                ),
            },
        ),
    }
}


#[tauri::command]
pub async fn messaging_register_account(
    request: MessagingRegisterAccountRequest,
) -> Result<
    MessagingRegisterAccountResponse,
    String,
> {
    let user_id =
        clean_user_id(&request.user_id)?;

    let username =
        clean_username(&request.username)?;

    let password =
        clean_password(&request.password)?;

    let registration_token =
        read_registration_token()?;

    let client =
        build_messaging_client().await?;

    let response =
        register_with_token(
            &client,
            &username,
            &password,
            &registration_token,
        )
        .await?;

    /*
     * Never return:
     *   access_token
     *   refresh_token
     *   password
     *   registration token
     */

    Ok(
        MessagingRegisterAccountResponse {
            status: "active".to_string(),
            user_id,
            messaging_user_id:
                response.user_id.to_string(),
            device_id:
                response
                    .device_id
                    .map(
                        |value|
                            value.to_string()
                    ),
        },
    )
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateInitialAdminRequest {
    pub username: String,
    pub email: String,
    pub password: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateApplicationAccountResponse {
    pub status: String,
    pub user_id: String,
    pub username: String,
    pub email: String,
    pub role: String,
    pub messaging_user_id: String,
}


fn project_root() -> Result<PathBuf, String> {
    let manifest_directory =
        PathBuf::from(env!("CARGO_MANIFEST_DIR"));

    manifest_directory
        .parent()
        .and_then(Path::parent)
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .ok_or_else(|| {
            "DataWorc project root could not be resolved."
                .to_string()
        })
}


fn python_executable(
    root: &Path,
) -> PathBuf {
    root
        .join("venv")
        .join("bin")
        .join("python")
}


fn run_account_bridge(
    arguments: &[String],
) -> Result<Value, String> {
    let root = project_root()?;
    let python = python_executable(&root);

    if !python.is_file() {
        return Err(
            "Configured Python interpreter was not found."
                .to_string()
        );
    }

    let output = Command::new(python)
        .current_dir(&root)
        .env("PYTHONPATH", &root)
        .arg("-m")
        .arg(
            "engine.accounts.application_bridge"
        )
        .args(arguments)
        .output()
        .map_err(|error| {
            format!(
                "Account service could not be started: {error}"
            )
        })?;

    let stdout =
        String::from_utf8_lossy(
            &output.stdout
        )
        .trim()
        .to_string();

    if stdout.is_empty() {
        return Err(
            "Account service returned no response."
                .to_string()
        );
    }

    let value: Value =
        serde_json::from_str(&stdout)
            .map_err(|error| {
                format!(
                    "Account service returned invalid JSON: {error}"
                )
            })?;

    if !output.status.success() {
        let message = value
            .get("error")
            .and_then(Value::as_str)
            .unwrap_or(
                "Account operation failed."
            );

        return Err(message.to_string());
    }

    Ok(value)
}


fn account_status(
    user_id: &str,
    status: &str,
) -> Result<Value, String> {
    run_account_bridge(&[
        "set-status".to_string(),
        "--user-id".to_string(),
        user_id.to_string(),
        "--status".to_string(),
        status.to_string(),
    ])
}


fn bind_messaging_identity(
    user_id: &str,
    messaging_user_id: &str,
) -> Result<Value, String> {
    run_account_bridge(&[
        "bind-messaging-identity".to_string(),
        "--user-id".to_string(),
        user_id.to_string(),
        "--messaging-user-id".to_string(),
        messaging_user_id.to_string(),
    ])
}


#[tauri::command]
pub fn has_admin_account(
) -> Result<bool, String> {
    let response =
        run_account_bridge(&[
            "has-active-admin".to_string(),
        ])?;

    Ok(
        response
            .get("has_active_admin")
            .and_then(Value::as_bool)
            .unwrap_or(false)
    )
}


#[tauri::command]
pub async fn create_initial_admin(
    request: CreateInitialAdminRequest,
) -> Result<
    CreateApplicationAccountResponse,
    String,
> {
    if has_admin_account()? {
        return Err(
            "An active administrator already exists."
                .to_string()
        );
    }

    let username =
        clean_username(
            &request.username
        )?;

    let email =
        request.email
            .trim()
            .to_string();

    if email.is_empty() {
        return Err(
            "Email is required."
                .to_string()
        );
    }

    let password =
        clean_password(
            &request.password
        )?;

    let prepared =
        run_account_bridge(&[
            "prepare-account".to_string(),
            "--username".to_string(),
            username.clone(),
            "--email".to_string(),
            email.clone(),
            "--role".to_string(),
            "admin".to_string(),
        ])?;

    let account =
        prepared
            .get("account")
            .ok_or_else(|| {
                "Account service did not return an account."
                    .to_string()
            })?;

    let user_id =
        account
            .get("user_id")
            .and_then(Value::as_str)
            .ok_or_else(|| {
                "Account service did not return user_id."
                    .to_string()
            })?
            .to_string();

    let previous_status =
        account
            .get("status")
            .and_then(Value::as_str)
            .unwrap_or("");

    account_status(
        &user_id,
        "provisioning",
    )?;

    let messaging_user_id =
        if previous_status
            == "binding_failed"
        {
            format!(
                "@{}:{}",
                username,
                messaging_server_name()
            )
        } else {
            let registration_token =
                read_registration_token()?;

            let client =
                Client::builder()
                    .homeserver_url(
                        messaging_homeserver_url()
                    )
                    .disable_well_known_lookup(
                        true
                    )
                    .build()
                    .await
                    .map_err(|error| {
                        format!(
                            "Messaging client could not be created: {error}"
                        )
                    })?;

            let response =
                match register_with_token(
                    &client,
                    &username,
                    &password,
                    &registration_token,
                )
                .await
                {
                    Ok(value) => value,

                    Err(error) => {
                        let _ =
                            account_status(
                                &user_id,
                                "provisioning_failed",
                            );

                        return Err(error);
                    }
                };

            response.user_id.to_string()
        };

    if let Err(error) =
        bind_messaging_identity(
            &user_id,
            &messaging_user_id,
        )
    {
        let _ =
            account_status(
                &user_id,
                "binding_failed",
            );

        return Err(error);
    }

    account_status(
        &user_id,
        "active",
    )?;

    Ok(
        CreateApplicationAccountResponse {
            status: "active".to_string(),
            user_id,
            username,
            email,
            role: "admin".to_string(),
            messaging_user_id,
        }
    )
}
