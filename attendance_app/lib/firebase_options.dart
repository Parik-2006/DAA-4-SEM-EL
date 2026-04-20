import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      return web;
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      case TargetPlatform.macOS:
        return macos;
      case TargetPlatform.windows:
        throw UnsupportedError(
          'DefaultFirebaseOptions has not been configured for windows - '
          'you can reconfigure this by running the FlutterFire CLI again.',
        );
      case TargetPlatform.linux:
        throw UnsupportedError(
          'DefaultFirebaseOptions has not been configured for linux - '
          'you can reconfigure this by run the FlutterFire CLI again.',
        );
      default:
        throw UnsupportedError(
          'DefaultFirebaseOptions has not been configured for ${defaultTargetPlatform.name} - '
          'you can reconfigure this by running the FlutterFire CLI again.',
        );
    }
  }

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyAIVYy3iymGvfWt9LL99nyvakXNACHtY-E',
    appId: '1:103216880346:android:7c194987d4b1bcf08be3e3',
    messagingSenderId: '103216880346',
    projectId: 'daa-4th-sem',
    storageBucket: 'daa-4th-sem.firebasestorage.app',
  );

  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: 'AIzaSyCIhj8BL32dRQt31EcO0KUgj7ahvOrk9cU',
    appId: '1:103216880346:ios:a9ad9cdd0423d6a48be3e3',
    messagingSenderId: '103216880346',
    projectId: 'daa-4th-sem',
    storageBucket: 'daa-4th-sem.firebasestorage.app',
  );

  static const FirebaseOptions macos = FirebaseOptions(
    apiKey: 'AIzaSyCIhj8BL32dRQt31EcO0KUgj7ahvOrk9cU',
    appId: '1:103216880346:macos:a9ad9cdd0423d6a48be3e3',
    messagingSenderId: '103216880346',
    projectId: 'daa-4th-sem',
    storageBucket: 'daa-4th-sem.firebasestorage.app',
  );

  static const FirebaseOptions web = FirebaseOptions(
    apiKey: 'AIzaSyCIhj8BL32dRQt31EcO0KUgj7ahvOrk9cU',
    appId: '1:103216880346:web:a9ad9cdd0423d6a48be3e3',
    messagingSenderId: '103216880346',
    projectId: 'daa-4th-sem',
    storageBucket: 'daa-4th-sem.firebasestorage.app',
  );
}
