import { invoke } from "@tauri-apps/api/core";

export type MessagingStatus = {
  status: string;
  available?: boolean;
  serverName?: string;
  homeserverUrl?: string;
  detail?: string;
};

export type CreateInitialAdminInput = {
  username: string;
  email: string;
  password: string;
};

export type CreatedAccount = {
  status: string;
  userId: string;
  username: string;
  email: string;
  role: string;
  messagingUserId: string;
};

export async function hasAdminAccount(): Promise<boolean> {
  return invoke<boolean>("has_admin_account");
}

export async function getMessagingStatus(): Promise<MessagingStatus> {
  return invoke<MessagingStatus>(
    "get_messaging_status"
  );
}

export async function createInitialAdmin(
  input: CreateInitialAdminInput
): Promise<CreatedAccount> {
  return invoke<CreatedAccount>(
    "create_initial_admin",
    {
      request: input,
    }
  );
}
