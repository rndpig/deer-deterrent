// Firebase configuration
import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';

const firebaseConfig = {
  apiKey: "AIzaSyCR5aY3ujftYYBidjp1H_N3uXYwGOAvWDU",
  authDomain: "deer-deterrent-rnp.firebaseapp.com",
  projectId: "deer-deterrent-rnp",
  storageBucket: "deer-deterrent-rnp.firebasestorage.app",
  messagingSenderId: "427707371016",
  appId: "1:427707371016:web:cdae5e1d06a0bdf0818bbd"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Firebase Authentication
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
