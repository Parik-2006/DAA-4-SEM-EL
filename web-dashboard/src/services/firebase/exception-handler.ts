export class FirebaseException extends Error {
  constructor(public userMessage: string, public code?: string) {
    super(userMessage);
    this.name = 'FirebaseException';
  }
}
