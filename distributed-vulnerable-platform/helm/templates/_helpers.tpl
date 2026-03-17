{{/*
Common labels
*/}}
{{- define "dvp.labels" -}}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: dvp
{{- end -}}

{{/*
Full name prefix
*/}}
{{- define "dvp.fullname" -}}
{{ .Release.Name }}
{{- end -}}

{{/*
Database URL for a given service db name
*/}}
{{- define "dvp.dbUrl" -}}
postgresql://{{ .Values.postgres.user }}:{{ .Values.postgres.password }}@{{ include "dvp.fullname" . }}-postgres:5432/{{ . | toString }}
{{- end -}}
