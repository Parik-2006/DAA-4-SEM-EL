// firebase.ts
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";

const firebaseConfig = {
  apiKey: "AIzaSyCIhj8BL32dRQt31EcO0KUgj7ahvOrk9cU",
  authDomain: "daa-4th-sem.firebaseapp.com",
  projectId: "daa-4th-sem",
  storageBucket: "daa-4th-sem.firebasestorage.app",
  messagingSenderId: "103216880346",
  appId: "1:103216880346:web:a9ad9cdd0423d6a48be3e3",
  measurementId: "G-SM63TDEWC7"
};

const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);

export { app, analytics };