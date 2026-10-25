/**
 * The server turned the sign-in away for now (429): this account, or this network,
 * signed in too often this minute. Its body is English, and the login screen showed it
 * as it came, in every language; the screen shows its own translated line instead.
 */
export class SignInLimitedError extends Error {
  constructor() {
    super("sign_in_limited");
    this.name = "SignInLimitedError";
  }
}
