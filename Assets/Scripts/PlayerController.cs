using UnityEngine;
using UnityEngine.Animations;

public class PlayerController : MonoBehaviour
{
    private Animator animator;
    private string currentAnimationClip = "";
    private float currentSpeed = 0.0f;

    [Range(0f, 10f)]
    public float walkSpeed = 3.0f;
    public AnimationClip idleLeftAnimation = null;
    public AnimationClip idleRightAnimation = null;
    public AnimationClip walkLeftAnimation = null;
    public AnimationClip walkRightAnimation = null;

    // Start is called before the first frame update
    void Start()
    {
        animator = GetComponent <Animator>();
    }

    // Update is called once per frame
    void Update()
    {
        MoveAndAnimate();
        currentSpeed = Input.GetAxis("Horizontal");
        animator.SetFloat("Speed", currentSpeed);
    }

    // Check if the animation clip is valid and play it
    void PlayAnimation(AnimationClip animationClip)
    {
        if(animationClip == null)
        {
            Debug.LogWarning("AnimationClip '" + animationClip.name + "' not provided to PlayerController");
            return;
        }
        if(animationClip.name == currentAnimationClip)
        {
            return;
        }
        animator.Play(animationClip.name);
        currentAnimationClip = animationClip.name;
    }

    // Determine what animation should be played and update position
    void MoveAndAnimate()
    {
        if(Input.GetKey(KeyCode.D))
        {
            PlayAnimation(walkRightAnimation);
            transform.Translate(Vector2.right * walkSpeed * Time.deltaTime);
        }
        else if(Input.GetKeyUp(KeyCode.D))
        {
            PlayAnimation(idleRightAnimation);
        }
        else if(Input.GetKey(KeyCode.A))
        {
            PlayAnimation(walkLeftAnimation);
            transform.Translate(Vector2.left * walkSpeed * Time.deltaTime);
            // Rotate sprite (could be useful for reverted side movement sprite)
            //transform.eulerAngles = new Vector2(0, 0);
        }
        else if(Input.GetKeyUp(KeyCode.A))
        {
            PlayAnimation(idleLeftAnimation);
        }
    }
}
