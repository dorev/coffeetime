using UnityEngine.Audio;
using UnityEngine;

[System.Serializable]
public class Sound
{
    [HideInInspector]
    public AudioSource source;
    public AudioClip clip;
    public string name;
    
    [Range(0f, 1f)]
    public float volume;
    public bool loop;

    public Sound()
    {
        // Default volume at 50%
        volume = 0.5f;
    }

    public void Play()
    {
        if(source == null)
        {
            return;
        }
        source.Play();
    }

    public void Stop()
    {
        if(source == null)
        {
            return;
        }
        source.Stop();
    }

    public bool isPlaying { get { return IsPlaying(); } }

    private bool IsPlaying()
    {
        if(source == null)
        {
            return false;
        }
        return source.isPlaying;
    }
}
