/* Public config — client_id is not a secret.
   Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Web client
   Authorized JavaScript origins must include:
     https://hristos0527.github.io
     http://localhost:8080   (local preview)
*/
window.KAIROS_CONFIG = {
  // Personal GCP OAuth Web client (same family as workspace-personal MCP)
  clientId: '889345739957-avtk5njo2d1ai1gc5259f4e71jja0tu0.apps.googleusercontent.com',
  scopes: [
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/calendar.events',
  ].join(' '),
  taskListId: '@default',
  kairosCalendarId:
    '73661aa7f8ac58bd811558f8cbed7d3b30dfc104a1c5d1fd3a884220d742e26d@group.calendar.google.com',
  timeZone: 'Europe/Budapest',
  // Override: ?client_id=YOUR_WEB_CLIENT_ID.apps.googleusercontent.com
};
