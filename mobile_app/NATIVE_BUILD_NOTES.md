# Android / iOS native project generation

This source package includes the Capacitor 8 config and the script to generate **both** platform projects.  Because npm registry downloads were unavailable in the authoring environment, this zip does **not** claim to contain generated `android/` and `ios/` directories, APK, or IPA.

Run on a networked development machine (Node 22+):

```bash
cd mobile_app
cp .env.example .env    # replace with your ACTUAL https API origin
npm install
npm run build
npm run native:init     # creates Android here; also iOS when run on macOS
```

For Android, install Android Studio + SDK, then `npm run android` and build APK in Android Studio. For iOS, use macOS with Xcode 26+, then `npm run ios`, set signing team and distribute via TestFlight/enterprise-approved method. No Apple signing keys are bundled.

Do not use `server.url` in production or set `cleartext`/`allowMixedContent` to true. On Android, HTTP localhost is used only for the *local WebView origin*, while remote API must use HTTPS.

**On macOS**: run `npx cap add ios` if you first generated Android on Linux/Windows. Capacitor 8 needs Xcode 26+.
