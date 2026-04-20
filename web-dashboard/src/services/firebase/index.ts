// src/services/firebase/index.ts
export { default as auth, signUp, signIn, signOut, getCurrentUser, onAuthChange, getAuthToken } from './auth.service';
export type { } from './auth.service';

export {
  default as db,
  addDocument,
  getDocument,
  queryDocuments,
  getAllDocuments,
  updateDocument,
  deleteDocument,
  getStudentAttendance,
  getCourseAttendance,
  getAllStudents,
  getAllCourses,
} from './firestore.service';
export type { AttendanceRecord, Student, Course } from './firestore.service';

export {
  default as storage,
  uploadFile,
  uploadFileWithProgress,
  getFileUrl,
  deleteFile,
  uploadStudentAvatar,
  uploadAttendancePhoto,
} from './storage.service';
export type { UploadProgress } from './storage.service';
