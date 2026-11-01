/* Illustrative Feishu H5 page snippet. NOT a bundled login page.
 * Load/configure Feishu H5 SDK per its official instructions first.
 * `appId` is public; NEVER put App Secret in browser source.
 * Same-origin HTTPS routing: /platform/v1 -> platform service /v1.
 */
function loginFromFeishu(appId) {
  if (!window.tt?.requestAuthCode) throw new Error('Please open inside Feishu mobile client');
  window.tt.requestAuthCode({
    appId,
    success: async ({code}) => {
      const response = await fetch('/platform/v1/auth/feishu/exchange', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({code}),
      });
      if (!response.ok) throw new Error('Your account is not authorized or Feishu verification failed');
      const {user} = await response.json();
      console.log('Signed in as', user.display_name);
    },
    fail: () => { throw new Error('Feishu authorization not available'); },
  });
}
