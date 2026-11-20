import { useCallback, useEffect, useState } from 'react';
import { Alert, Pressable, StyleSheet, Switch, Text, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import { CameraView } from 'expo-camera';
import { MAX_UPLOAD_BYTES, PortfolioLinkSchema, type Document } from '@careerfit/shared';
import { ConsentGate } from '@/components/Consent';
import { DEMO_APP, DemoNotice } from '@/components/Demo';
import { Badge, Body, Button, Card, Field, Heading, Muted, Notice, Screen } from '@/components/ui';
import { useI18n, type TextKey } from '@/i18n';
import { api } from '@/lib/api';
import { documentState } from '@/lib/labels';
import { colors, MIN_TOUCH, radius, space, type } from '@/theme';

const POLL_MS = 2000;
const PDF = 'application/pdf';
const DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

const TYPE_LABEL: Record<Document['type'], TextKey> = {
  resume: 'documents.typeResume',
  cover_letter: 'documents.typeCoverLetter',
  portfolio_link: 'documents.typePortfolio',
};

type Upload = { uri: string; name: string; mimeType: string; size?: number };

export default function DocumentsScreen() {
  const i18n = useI18n();
  const { t, date } = i18n;
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [link, setLink] = useState('');
  const [linkError, setLinkError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const [demo, setDemo] = useState(false);

  const load = useCallback(async () => {
    // The public demo offers a made-up resume; elsewhere this stays false.
    api.account
      .plan()
      .then((plan) => setDemo(plan.demo))
      .catch(() => undefined);
    try {
      setDocuments(await api.documents.list());
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const busy = documents?.some((document) => documentState(i18n, document).busy) ?? false;
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => void load(), POLL_MS);
    return () => clearInterval(timer);
  }, [busy, load]);

  async function refresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  async function upload(file: Upload) {
    setUploadError(null);
    setUploadMessage(null);
    if (file.size !== undefined && file.size > MAX_UPLOAD_BYTES) {
      setUploadError(t('documents.tooLarge'));
      return;
    }
    const form = new FormData();
    form.append('type', 'resume');
    // React Native reads the file from this uri; its FormData accepts this shape.
    form.append('file', { uri: file.uri, name: file.name, type: file.mimeType } as unknown as Blob);
    setProgress(0);
    try {
      await api.documents.upload(form, setProgress);
      setUploadMessage(t('documents.uploaded'));
      await load();
    } catch (error) {
      setUploadError(i18n.errorText(error, 'documents.uploadFailed'));
    }
    setProgress(null);
  }

  async function addSample() {
    setUploadError(null);
    setUploadMessage(null);
    setProgress(0);
    try {
      await api.documents.addSample();
      setUploadMessage(t('demo.sampleAdded'));
      await load();
    } catch (error) {
      setUploadError(i18n.errorText(error, 'demo.sampleFailed'));
    }
    setProgress(null);
  }

  async function chooseFile() {
    const picked = await DocumentPicker.getDocumentAsync({
      type: [PDF, DOCX],
      copyToCacheDirectory: true,
    });
    const file = picked.assets?.[0];
    if (picked.canceled || !file) return;
    await upload({
      uri: file.uri,
      name: file.name,
      mimeType: file.mimeType ?? PDF,
      size: file.size,
    });
  }

  async function scan() {
    setUploadError(null);
    try {
      // The phone's own scanner finds the page edges and straightens them, then hands back one PDF.
      const scanned = await CameraView.scanDocumentAsync({ requestPdf: true });
      if (!scanned) return;
      if (!scanned.pdfUri) {
        setUploadError(t('documents.scanUnavailable'));
        return;
      }
      await upload({ uri: scanned.pdfUri, name: t('documents.scannedName'), mimeType: PDF });
    } catch {
      setUploadError(t('documents.scanUnavailable'));
    }
  }

  async function addLink() {
    setLinkError(null);
    const url = link.trim();
    if (!url.startsWith('https://') || !PortfolioLinkSchema.safeParse({ url }).success) {
      setLinkError(t('documents.linkInvalid'));
      return;
    }
    try {
      await api.documents.addPortfolioLink({ url });
      setLink('');
      await load();
    } catch (error) {
      setLinkError(i18n.errorText(error, 'documents.linkFailed'));
    }
  }

  function setKeep(document: Document, keep: boolean) {
    api.documents
      .setKeep(document.id, keep)
      .then(load)
      .catch((error: unknown) => Alert.alert(i18n.errorText(error, 'documents.keepFailed')));
  }

  function retentionText(document: Document): string {
    // In the public demo the whole account goes after 30 days, before any file's 90 days are up.
    if (DEMO_APP) return t('demo.retention');
    if (document.fileDeletedAt)
      return t('documents.fileDeleted', { date: date(document.fileDeletedAt) });
    if (document.keep || !document.deleteAfter) return t('documents.kept');
    return t('documents.deleteAfter', { date: date(document.deleteAfter) });
  }

  function confirmDelete(document: Document) {
    const name = document.fileName ?? document.url ?? '';
    Alert.alert(
      t('documents.deleteTitle', { name }),
      document.type === 'resume' ? t('documents.deleteResumeBody') : t('documents.deleteBody'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('common.delete'),
          style: 'destructive',
          onPress: () => {
            api.documents
              .delete(document.id)
              .then(load)
              .catch(() => Alert.alert(t('documents.deleteFailed')));
          },
        },
      ],
    );
  }

  const uploading = progress !== null;

  return (
    <Screen onRefresh={() => void refresh()} refreshing={refreshing}>
      <DemoNotice />
      <ConsentGate>
        <Card>
          <Heading>{t('documents.title')}</Heading>
          <Body>{t('documents.intro')}</Body>
          <Button
            title={t('documents.chooseFile')}
            disabled={uploading}
            onPress={() => void chooseFile()}
          />
          <Button
            variant="secondary"
            title={t('documents.scan')}
            disabled={uploading}
            onPress={() => void scan()}
          />
          {demo && (
            <Button
              variant="secondary"
              title={t('demo.sampleAction')}
              disabled={uploading}
              onPress={() => void addSample()}
            />
          )}
          <Muted>{t('documents.fileHint')}</Muted>
          {uploading && (
            <View
              accessibilityRole="progressbar"
              accessibilityValue={{ min: 0, max: 100, now: Math.round(progress * 100) }}
              style={styles.progress}
            >
              <Muted>{t('documents.uploading', { percent: Math.round(progress * 100) })}</Muted>
              <View style={styles.track}>
                <View style={[styles.fill, { width: `${Math.round(progress * 100)}%` }]} />
              </View>
            </View>
          )}
          {uploadMessage && <Notice>{uploadMessage}</Notice>}
          {uploadError && <Notice tone="error">{uploadError}</Notice>}
          <Muted>{t('documents.privacy')}</Muted>
        </Card>
      </ConsentGate>

      <Card>
        <Heading>{t('documents.addedTitle')}</Heading>
        {loadFailed && <Notice tone="error">{t('documents.loadFailed')}</Notice>}
        {documents?.length === 0 && <Body>{t('documents.empty')}</Body>}
        {documents?.map((document) => {
          const state = documentState(i18n, document);
          const name = document.fileName ?? document.url ?? '';
          return (
            <View key={document.id} style={styles.row}>
              <View style={styles.flex}>
                <Text style={[type.body, styles.name]} numberOfLines={2}>
                  {name}
                </Text>
                <Muted>{t(TYPE_LABEL[document.type])}</Muted>
                <Badge label={state.label} tone={state.tone} />
                {document.type !== 'portfolio_link' && <Muted>{retentionText(document)}</Muted>}
                {document.type !== 'portfolio_link' && !document.fileDeletedAt && !DEMO_APP && (
                  <View style={styles.keepRow}>
                    <Switch
                      accessibilityLabel={`${t('documents.keepLabel')}: ${name}`}
                      value={document.keep}
                      onValueChange={(keep) => setKeep(document, keep)}
                      trackColor={{ true: colors.primary, false: colors.border }}
                      thumbColor={colors.card}
                    />
                    <Body>{t('documents.keepLabel')}</Body>
                  </View>
                )}
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={t('documents.deleteNamed', { name })}
                onPress={() => confirmDelete(document)}
                style={({ pressed }) => [styles.delete, pressed && styles.pressed]}
              >
                <Text style={styles.deleteText}>{t('common.delete')}</Text>
              </Pressable>
            </View>
          );
        })}
      </Card>

      <Card>
        <Heading>{t('documents.linkTitle')}</Heading>
        <Field
          label={t('documents.linkLabel')}
          placeholder="https://"
          value={link}
          onChangeText={setLink}
          error={linkError}
          hint={t('documents.linkHint')}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        <Button
          variant="secondary"
          title={t('documents.addLink')}
          disabled={!link.trim()}
          onPress={() => void addLink()}
        />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  keepRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  progress: { gap: space.xs },
  track: { height: 8, borderRadius: 4, backgroundColor: colors.secondary },
  fill: { height: 8, borderRadius: 4, backgroundColor: colors.primary },
  row: {
    flexDirection: 'row',
    gap: space.md,
    paddingTop: space.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  flex: { flex: 1, gap: space.xs },
  name: { fontWeight: '600', color: colors.foreground },
  delete: {
    minHeight: MIN_TOUCH,
    minWidth: MIN_TOUCH,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: space.sm,
    borderRadius: radius.sm,
  },
  deleteText: { color: colors.destructive, fontWeight: '600' },
  pressed: { opacity: 0.6 },
});
