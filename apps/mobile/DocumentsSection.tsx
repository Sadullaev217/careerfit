import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { apiErrorMessage, MAX_UPLOAD_BYTES, type ApiClient, type Document } from '@careerfit/shared';

const POLL_INTERVAL_MS = 2000;
const DOCX_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

const STATUS_LABELS: Record<Document['status'], string> = {
  pending: 'Waiting to be read…',
  parsing: 'Reading…',
  ready: 'Ready',
  failed: 'Failed',
};

const TYPE_LABELS: Record<Document['type'], string> = {
  resume: 'Resume',
  cover_letter: 'Cover letter',
  portfolio_link: 'Portfolio link',
};

export function DocumentsSection({ api }: { api: ApiClient }) {
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [link, setLink] = useState('');
  const [linkError, setLinkError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setDocuments(await api.documents.list());
      setLoadError(null);
    } catch {
      setLoadError('Could not load your documents.');
    }
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const processing = documents?.some((d) => d.status === 'pending' || d.status === 'parsing');

  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [processing, refresh]);

  async function pickAndUpload(docType: 'resume' | 'cover_letter') {
    setUploadError(null);
    const picked = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', DOCX_TYPE],
      copyToCacheDirectory: true,
    });
    const file = picked.assets?.[0];
    if (picked.canceled || !file) return;
    if (file.size !== undefined && file.size > MAX_UPLOAD_BYTES) {
      setUploadError('This file is larger than the 10 MB limit.');
      return;
    }

    const form = new FormData();
    form.append('type', docType);
    // React Native reads the file from this uri; its FormData accepts this shape.
    form.append('file', {
      uri: file.uri,
      name: file.name,
      type: file.mimeType ?? 'application/octet-stream',
    } as unknown as Blob);
    setProgress(0);
    try {
      await api.documents.upload(form, setProgress);
      await refresh();
    } catch (error) {
      setUploadError(apiErrorMessage(error, 'The upload failed. Please try again.'));
    }
    setProgress(null);
  }

  async function addLink() {
    setLinkError(null);
    try {
      await api.documents.addPortfolioLink({ url: link.trim() });
      setLink('');
      await refresh();
    } catch (error) {
      setLinkError(apiErrorMessage(error, 'Could not add this link. Please try again.'));
    }
  }

  function confirmDelete(document: Document) {
    Alert.alert('Delete this?', document.fileName ?? document.url ?? '', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          api.documents
            .delete(document.id)
            .then(refresh)
            .catch((error: unknown) =>
              setLoadError(apiErrorMessage(error, 'Could not delete this. Please try again.')),
            );
        },
      },
    ]);
  }

  const uploading = progress !== null;

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
      <Text style={styles.heading}>Your documents</Text>
      <Text style={styles.hint}>PDF or DOCX, up to 10 MB.</Text>
      <Button
        title="Upload resume"
        disabled={uploading}
        onPress={() => void pickAndUpload('resume')}
      />
      <Button
        title="Upload cover letter"
        disabled={uploading}
        onPress={() => void pickAndUpload('cover_letter')}
      />
      {uploading && (
        <View
          accessibilityRole="progressbar"
          accessibilityValue={{ min: 0, max: 100, now: Math.round(progress * 100) }}
        >
          <Text>Uploading… {Math.round(progress * 100)}%</Text>
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${Math.round(progress * 100)}%` }]} />
          </View>
        </View>
      )}
      {uploadError && (
        <Text accessibilityRole="alert" style={styles.error}>
          {uploadError}
        </Text>
      )}

      <Text style={styles.heading}>Add a portfolio link</Text>
      <Text style={styles.hint}>LinkedIn is saved as a link only and is not read.</Text>
      <TextInput
        style={styles.input}
        placeholder="https://"
        accessibilityLabel="Portfolio address"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        value={link}
        onChangeText={setLink}
      />
      <Button title="Add link" disabled={!link.trim()} onPress={() => void addLink()} />
      {linkError && (
        <Text accessibilityRole="alert" style={styles.error}>
          {linkError}
        </Text>
      )}

      <Text style={styles.heading}>Added so far</Text>
      {loadError && (
        <Text accessibilityRole="alert" style={styles.error}>
          {loadError}
        </Text>
      )}
      {documents === null && !loadError && <Text>Loading…</Text>}
      {documents?.length === 0 && <Text>Nothing here yet. Upload your resume to get started.</Text>}
      {documents?.map((document) => (
        <View key={document.id} style={styles.row}>
          <Text style={styles.rowTitle}>{document.fileName ?? document.url}</Text>
          <Text style={styles.hint}>{TYPE_LABELS[document.type]}</Text>
          <Text>{STATUS_LABELS[document.status]}</Text>
          {document.errorMessage && <Text style={styles.error}>{document.errorMessage}</Text>}
          <Button title="Delete" color="#dc2626" onPress={() => confirmDelete(document)} />
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { alignSelf: 'stretch', flex: 1 },
  content: { gap: 12, paddingBottom: 24 },
  heading: { fontSize: 18, fontWeight: '600', marginTop: 8 },
  hint: { color: '#52525b' },
  error: { color: '#dc2626' },
  input: { borderWidth: 1, borderColor: '#a1a1aa', borderRadius: 6, padding: 10 },
  track: { height: 8, borderRadius: 4, backgroundColor: '#e4e4e7', marginTop: 4 },
  fill: { height: 8, borderRadius: 4, backgroundColor: '#2563eb' },
  row: { borderWidth: 1, borderColor: '#a1a1aa', borderRadius: 6, padding: 12, gap: 6 },
  rowTitle: { fontWeight: '600' },
});
