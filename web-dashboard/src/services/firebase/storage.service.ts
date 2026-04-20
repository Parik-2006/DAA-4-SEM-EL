// src/services/firebase/storage.service.ts
import {
  getStorage,
  ref,
  uploadBytes,
  uploadBytesResumable,
  downloadURL,
  deleteObject,
  UploadTask,
} from 'firebase/storage';
import { app } from '@/firebase';

const storage = getStorage(app);

export interface UploadProgress {
  bytesTransferred: number;
  totalBytes: number;
  progress: number;
}

/**
 * Upload a file to Firebase Storage
 */
export const uploadFile = async (
  filePath: string,
  file: File
): Promise<string> => {
  try {
    const storageRef = ref(storage, filePath);
    await uploadBytes(storageRef, file);
    const downloadUrl = await downloadURL(storageRef);
    return downloadUrl;
  } catch (error: any) {
    console.error('Error uploading file:', error);
    throw error;
  }
};

/**
 * Upload file with progress tracking
 */
export const uploadFileWithProgress = (
  filePath: string,
  file: File,
  onProgress: (progress: UploadProgress) => void
): UploadTask => {
  const storageRef = ref(storage, filePath);
  const uploadTask = uploadBytesResumable(storageRef, file);

  uploadTask.on('state_changed', (snapshot) => {
    const progress = (snapshot.bytesTransferred / snapshot.totalBytes) * 100;
    onProgress({
      bytesTransferred: snapshot.bytesTransferred,
      totalBytes: snapshot.totalBytes,
      progress,
    });
  });

  return uploadTask;
};

/**
 * Get download URL for a file
 */
export const getFileUrl = async (filePath: string): Promise<string> => {
  try {
    const storageRef = ref(storage, filePath);
    return await downloadURL(storageRef);
  } catch (error: any) {
    console.error('Error getting file URL:', error);
    throw error;
  }
};

/**
 * Delete a file from Storage
 */
export const deleteFile = async (filePath: string): Promise<void> => {
  try {
    const storageRef = ref(storage, filePath);
    await deleteObject(storageRef);
  } catch (error: any) {
    console.error('Error deleting file:', error);
    throw error;
  }
};

/**
 * Upload student avatar
 */
export const uploadStudentAvatar = async (
  studentId: string,
  file: File
): Promise<string> => {
  return uploadFile(`students/${studentId}/avatar`, file);
};

/**
 * Upload attendance photo
 */
export const uploadAttendancePhoto = async (
  attendanceId: string,
  file: File
): Promise<string> => {
  return uploadFile(`attendance/${attendanceId}/photo`, file);
};

export default storage;
